#!/usr/bin/env python3
"""MEMO リポジトリ用ツール（標準ライブラリのみ）。仕組みの解説はリポジトリ直下の memo-detail.md

使い方（どのディレクトリから実行してもよい）:
  python3 scripts/memo.py new   NAME                  テンプレートから src/NAME.html を作る
  python3 scripts/memo.py add   SRC NAME [--force]    外部の HTML を src/NAME.html として取り込む
  python3 scripts/memo.py path  NAME [--md]           src/NAME.html（--md なら dist/md/NAME.md）の絶対パスを表示
  python3 scripts/memo.py url   [NAME]                公開 URL を表示（src/CNAME、なければ GitHub Pages の URL）
  python3 scripts/memo.py lint  MEMO... [--fix] [--backlink]
  python3 scripts/memo.py meta  MEMO [--title T] [--desc D] [--tags a,b] [--date YYYY-MM-DD]
  python3 scripts/memo.py build [--check]             src/ から公開用のサイト一式を dist/ に書き出す（--check は古いかだけ見る）
  python3 scripts/memo.py list
  python3 scripts/memo.py config [KEY]                memo.config.json の設定を表示（例: config branch）
  python3 scripts/memo.py preview MEMO|index|roadmap|FILE [-o OUT]   会話内プレビュー用に 1 枚へ埋め込んだ HTML を作る

MEMO / NAME は「docker」「docker.html」「src/docker.html」のどれでもよい
（既存のファイルパスを渡した場合はそのファイルを対象にする）。
置き場所（src/・dist/）やテンプレートの場所はこのスクリプトだけが知っている。
サイト名・リポジトリ・ブランチ・タイムゾーンなど、サイトごとの値はリポジトリ直下の memo.config.json に書く。

メモ = src/ 直下の *.html（index.html・roadmap.html 以外）。src/ は原本だけを置く場所で、
build は src/ を読むだけで書き換えない。公開するのは build が書き出す dist/（Actions が dist ブランチにデプロイする）。
一覧情報は各メモの <head> 内の次のタグから読み取る:
  <title>                         タイトル（memo:title があればそちら優先）
  <meta name="description">       説明
  <meta name="memo:tags">         カンマ区切りのタグ
  <meta name="memo:date">         YYYY-MM-DD

build は一覧を dist/memos.json、Markdown 版を dist/md/ と dist/llms.txt に書き出し、
トップページはその一覧を読み込んで表示する。
あわせて、アプリ（claude.ai）に置く入口スキル dist/entry-skill/SKILL.md も memo.config.json から生成する。

このファイルはコマンドの入口だけで、処理の本体は scripts/memolib/ にある。
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import tempfile
from pathlib import Path

from memolib.config import (CONFIG, CONFIG_FILE, SRC, ROOT, SITE_URL, SPECIAL_NAMES, TEMPLATE,
                            read_text, repository_warning, today)
from memolib.dist import dist_outputs, sync_dist
from memolib.lint import lint_text
from memolib.markdown import MD_DIR
from memolib.meta import set_meta, memo_files, memo_path, read_meta
from memolib.site import strip_fence, preview_text

def cmd_lint(args) -> int:
    bad = 0
    for f in args.files:
        path = memo_path(f)
        text = read_text(path)
        new, fixed, problems = lint_text(text, args.backlink)
        print(f"== {path.name}")
        if fixed:
            verb = "修正" if args.fix else "修正可能"
            for n in fixed:
                print(f"  [{verb}] {n}")
        for p in problems:
            print(f"  [要対応] {p}")
        if not fixed and not problems:
            print("  OK")
        if args.fix and new != text:
            path.write_text(new, encoding="utf-8")
        if problems or (fixed and not args.fix):
            bad = 1
    return bad


def cmd_meta(args) -> int:
    path = memo_path(args.file)
    text = read_text(path)
    if args.title is not None:
        t = html.escape(args.title, quote=False)
        if re.search(r"<title>.*?</title>", text, re.I | re.S):
            text = re.sub(r"<title>.*?</title>", lambda _: f"<title>{t}</title>", text,
                          count=1, flags=re.I | re.S)
        else:
            m = re.search(r"<head[^>]*>", text, re.I)
            pos = m.end() if m else 0
            text = text[:pos] + f"\n<title>{t}</title>" + text[pos:]
    if args.desc is not None:
        text = set_meta(text, "description", args.desc)
    if args.tags is not None:
        tags = ", ".join(t.strip() for t in args.tags.split(",") if t.strip())
        text = set_meta(text, "memo:tags", tags)
    if args.date is not None:
        date = args.date or today()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            sys.exit(f"--date は YYYY-MM-DD で書いてください（例: 2026-01-05）: {date}")
        try:
            dt.date.fromisoformat(date)
        except ValueError:
            sys.exit(f"--date の日付がありえない値です: {date}")
        text = set_meta(text, "memo:date", date)
    path.write_text(text, encoding="utf-8")
    print(json.dumps(read_meta(path), ensure_ascii=False, indent=2))
    return 0


def cmd_build(args) -> int:
    """src/（原本）を読んで、公開するサイト一式を dist/ に書き出す。src/ は書き換えない。"""
    warning = repository_warning()
    if warning:
        print(warning, file=sys.stderr)
    want, n_memos = dist_outputs()
    added, changed, removed = sync_dist(want, args.check)
    names = added + changed + [f"{n}（削除）" for n in removed]
    summary = f"（{n_memos} 件）"
    if args.check:
        if names:
            shown = ", ".join(names[:10]) + (f" ほか {len(names) - 10} ファイル" if len(names) > 10 else "")
            print(f"dist/ が古いです: {shown}（python3 scripts/memo.py build を実行）")
            return 1
        print(f"dist/ は最新です{summary}")
        return 0
    if names:
        parts = [f"{label} {len(x)}" for label, x in (("追加", added), ("変更", changed), ("削除", removed)) if x]
        print(f"dist/ を更新: {'・'.join(parts)} ファイル{summary}")
    else:
        print(f"変更なし{summary}")
    return 0


def cmd_new(args) -> int:
    target = memo_path(args.name, must_exist=False)
    if target.exists():
        sys.exit(f"すでにあります: {target.relative_to(ROOT)}")
    target.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    print(target)
    return 0


def cmd_add(args) -> int:
    src = Path(args.src)
    if not src.is_file():
        sys.exit(f"見つかりません: {src}")
    target = memo_path(args.name, must_exist=False)
    if target.exists() and not args.force:
        sys.exit(f"すでにあります: {target.relative_to(ROOT)}（上書きは --force）")
    if src.resolve() != target.resolve():
        target.write_text(strip_fence(read_text(src)), encoding="utf-8")
    print(target)
    return 0


def cmd_path(args) -> int:
    path = memo_path(args.name, must_exist=False)
    print(MD_DIR / f"{path.stem}.md" if args.md else path)
    return 0


def cmd_url(args) -> int:
    name = memo_path(args.name, must_exist=False).name if args.name else ""
    print(SITE_URL + ("" if name in ("", "index.html") else name))
    return 0


def cmd_config(args) -> int:
    if args.key is None:
        print(json.dumps({**CONFIG, "site_url": SITE_URL}, ensure_ascii=False, indent=2))
        return 0
    if args.key == "site_url":
        print(SITE_URL)
        return 0
    if args.key not in CONFIG:
        print(f"{args.key} という設定はありません（{CONFIG_FILE.name}: {', '.join(CONFIG)}, site_url）", file=sys.stderr)
        return 1
    print(CONFIG[args.key])
    return 0


def cmd_list(_args) -> int:
    for p in memo_files():
        m = read_meta(p)
        print(f"{m['date'] or '----------'}  {m['file']:<28} {m['title']}  [{', '.join(m['tags'])}]")
    return 0


def cmd_preview(args) -> int:
    p = Path(args.src)
    if p.is_file():
        src = p.resolve()
    elif p.name.removesuffix(".html") + ".html" in SPECIAL_NAMES:
        src = SRC / (p.name.removesuffix(".html") + ".html")
    else:
        src = memo_path(args.src)
    out = Path(args.out) if args.out else Path(tempfile.gettempdir()) / "memo-preview" / src.name
    if out.resolve() == src:
        sys.exit("出力先が元のファイルと同じです（-o で別の場所を指定）")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(preview_text(strip_fence(read_text(src)), src.name), encoding="utf-8")
    print(out)
    return 0


# ----------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="MEMO（Claude の解説ページ置き場）用ツール")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="テンプレートから新しいメモを作る")
    p.add_argument("name")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("add", help="外部の HTML を src/ に取り込む")
    p.add_argument("src")
    p.add_argument("name")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("path", help="メモの絶対パスを表示")
    p.add_argument("name")
    p.add_argument("--md", action="store_true", help="Markdown 版（dist/md/NAME.md。build で作られる）のパス")
    p.set_defaults(func=cmd_path)

    p = sub.add_parser("url", help="公開 URL を表示（src/CNAME から決まる）")
    p.add_argument("name", nargs="?")
    p.set_defaults(func=cmd_url)

    p = sub.add_parser("lint", help="崩れチェック（--fix で修正）")
    p.add_argument("files", nargs="+")
    p.add_argument("--fix", action="store_true")
    p.add_argument("--backlink", action="store_true", help="フッターに「一覧に戻る」リンクを追加")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("meta", help="タイトル・説明・タグ・日付を設定")
    p.add_argument("file")
    p.add_argument("--title")
    p.add_argument("--desc")
    p.add_argument("--tags", help="カンマ区切り")
    p.add_argument("--date", nargs="?", const="", help="YYYY-MM-DD（値なしで今日。タイムゾーンは memo.config.json）")
    p.set_defaults(func=cmd_meta)

    p = sub.add_parser("build", help="src/ から公開用のサイト一式（ページ・一覧データ・Markdown 版・入口スキル）を dist/ に書き出す")
    p.add_argument("--check", action="store_true", help="書き出さずに、dist/ が最新かだけを見る")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("config", help="memo.config.json の設定を表示（KEY を付けるとその値だけ）")
    p.add_argument("key", nargs="?")
    p.set_defaults(func=cmd_config)

    p = sub.add_parser("list", help="メモ一覧を表示")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("preview", help="一覧データを埋め込んだ 1 枚の HTML を書き出す（会話内プレビュー用）")
    p.add_argument("src", help="メモ名・index・roadmap、または下書きの HTML ファイル")
    p.add_argument("-o", "--out", help="出力先（省略時は一時フォルダの memo-preview/）")
    p.set_defaults(func=cmd_preview)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
