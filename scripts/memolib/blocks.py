"""build が dist/ のページに差し込む自動生成ブロック（memo:head）と「一覧に戻る」フッター、
サイト設定の差し込み、旧クイズの片付け。原本（src/）には自動生成ブロックを置かない。"""
from __future__ import annotations

import html
import re

from .config import (CONFIG, HEAD_BEGIN, HEAD_END, HEAD_RE, OG_VERSION, OPTIONAL_PAGES, SITE_NAME, SITE_URL,
                     SPECIAL_NAMES, accents)
from .meta import parse_meta

BACKLINK_ID = "memo-backlink"
# ページ下部のフッターに置く「一覧に戻る」リンク。どのページの CSS にも依存しないよう、
# スタイルはすべてインラインで完結させる（独自の CSS 変数を参照しない）。
BACKLINK = (
    f'<footer id="{BACKLINK_ID}" '
    'style="max-width:880px;margin:40px auto 0;padding:16px;text-align:center">'
    '<a href="index.html" style="display:inline-block;padding:6px 14px;border-radius:999px;'
    "background:rgba(127,127,127,.15);color:inherit;font:600 12px/1.4 ui-monospace,Menlo,monospace;"
    'letter-spacing:.08em;text-decoration:none;opacity:.85">&larr; 一覧に戻る</a></footer>'
)


# ---------------------------------------------------------------- head（アイコン・OGP）

def head_block(text: str, filename: str) -> str:
    m, title = parse_meta(text)
    title = (m.get("memo:title") or title or SITE_NAME).strip()
    desc = m.get("description", "").strip()
    is_index = filename == "index.html"
    url = SITE_URL + ("" if is_index else filename)
    e = lambda v: html.escape(v, quote=True)
    lines = [
        HEAD_BEGIN,
        '<link rel="icon" href="assets/favicon.ico" sizes="any">',
        '<link rel="icon" type="image/png" sizes="32x32" href="assets/icon-32.png">',
        '<link rel="icon" type="image/png" sizes="192x192" href="assets/icon-192.png">',
        '<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">',
        f'<meta name="apple-mobile-web-app-title" content="{SITE_NAME}">',
        f'<meta property="og:type" content="{"website" if is_index else "article"}">',
        f'<meta property="og:site_name" content="{SITE_NAME}">',
        f'<meta property="og:title" content="{e(title)}">',
    ]
    if desc:
        lines.append(f'<meta property="og:description" content="{e(desc)}">')
    lines += [
        f'<meta property="og:url" content="{e(url)}">',
        f'<meta property="og:image" content="{SITE_URL}assets/og.png' + (f'?v={OG_VERSION}' if OG_VERSION else '') + '">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        accent_style(),
        HEAD_END,
    ]
    return "\n".join(lines) + "\n"


def accent_style() -> str:
    """memo.config.json の branding のアクセント色で、ページの --accent を上書きする。
    各ページは :root と @media (prefers-color-scheme: dark) の :root で --accent を決めているので、
    それより強い html:root で書く（ブロックの位置がページの <style> の前でも後でも効く）。"""
    light, dark = accents()
    return (f'<style id="memo-accent">html:root{{--accent:{light}}}'
            f'@media (prefers-color-scheme: dark){{html:root{{--accent:{dark}}}}}</style>')


def apply_head(text: str, filename: str) -> str:
    block = head_block(text, filename)
    if HEAD_RE.search(text):
        return HEAD_RE.sub(lambda _: block, text, count=1)
    m = re.search(r"</head>", text, re.I)
    if m:
        return text[: m.start()] + block + text[m.start():]
    m = re.search(r"<head[^>]*>", text, re.I)
    pos = m.end() if m else 0
    return text[:pos] + "\n" + block + text[pos:]


# ---------------------------------------------------------------- 旧クイズの片付け
#
# 確認クイズの機能は廃止した。以前のメモに残っている表示ブロック（<!-- memo:quiz -->）と
# 問題データ（<script type="application/json" id="memo-quiz">）は lint・build が取り除く。

QUIZ_RE = re.compile(r"<!-- memo:quiz.*?<!-- /memo:quiz -->\n?", re.S)
QUIZ_DATA_RE = re.compile(
    r"<script\b[^>]*\bid=[\"']memo-quiz[\"'][^>]*>.*?</script>\n?", re.S | re.I)


def strip_quiz(text: str) -> str:
    """旧クイズの表示ブロックと問題データを取り除く（無ければそのまま）。"""
    return QUIZ_DATA_RE.sub("", QUIZ_RE.sub("", text))


# ---------------------------------------------------------------- サイト設定の差し込み
#
# トップ・設定・ロードマップページの「サイト名」「説明」「リポジトリへのリンク」「今のアクセント色」は
# memo.config.json から入れる（使える名前は site_fields()）。
# ページ側では書き換えたい要素に属性で目印を付ける（値は {site_name} などを埋め込んだ書式）。
#   <h1 data-memo-site="{site_name}">…</h1>                → 要素の中身（テキスト）を置き換える
#   <a href="…" data-memo-site-href="https://…/{repository}">  → 同じタグの href 属性を置き換える
#   <meta … content="…" data-memo-site-content="{description}"> → content 属性を置き換える
# 目印の属性はそのまま残るので、何度 build しても同じ結果になる。
# オプションのページへのリンクなどには data-memo-if="項目" を付ける（項目は config.OPTIONAL_PAGES の値）。
# memo.config.json でその項目がオフなら、要素ごと取り除く（オンなら何もしない）。
#   <span data-memo-if="roadmap">· <a href="roadmap.html">ロードマップ</a></span>
# 中に同じ名前のタグを入れ子にしない（最初の閉じタグまでを 1 つの要素とみなす）。

SITE_TEXT_RE = re.compile(r'(<([a-zA-Z][\w-]*)\b[^>]*?\sdata-memo-site="([^"]*)"[^>]*>)(.*?)(</\2\s*>)', re.S)
SITE_TAG_RE = re.compile(r'<[a-zA-Z][\w-]*\b[^>]*\sdata-memo-site-[a-z]+="[^"]*"[^>]*>')
SITE_ATTR_RE = re.compile(r'\sdata-memo-site-([a-z]+)="([^"]*)"')
SITE_IF_RE = re.compile(r'[ \t]*<([a-zA-Z][\w-]*)\b[^>]*?\sdata-memo-if="([^"]*)"[^>]*>.*?</\1\s*>[ \t]*\n?', re.S)


def site_fields() -> dict[str, str]:
    light, dark = accents()
    return {"site_name": CONFIG["site_name"], "description": CONFIG["description"],
            "repository": CONFIG["repository"], "branch": CONFIG["branch"],
            "accent": dark, "accent_light": light}


def _fill(template: str) -> str:
    try:
        return html.unescape(template).format(**site_fields())
    except (KeyError, IndexError, ValueError) as e:
        raise SystemExit(f"data-memo-site の書式が読めない: {template!r}（使える名前: "
                         + ", ".join("{" + k + "}" for k in site_fields()) + f"）: {e}")


def _keep_if(key: str) -> bool:
    if key not in OPTIONAL_PAGES.values():
        raise SystemExit(f"data-memo-if の項目が知らないもの: {key!r}（使える項目: {', '.join(OPTIONAL_PAGES.values())}）")
    return bool(CONFIG[key])


def apply_site(text: str) -> str:
    """data-memo-site の目印が付いた要素・属性を memo.config.json の値で置き換え、
    data-memo-if の付いた要素をオフの項目なら取り除く。"""
    text = SITE_IF_RE.sub(lambda m: m.group(0) if _keep_if(m.group(2)) else "", text)
    text = SITE_TEXT_RE.sub(
        lambda m: m.group(1) + html.escape(_fill(m.group(3)), quote=False) + m.group(5), text)

    def tag(m: re.Match) -> str:
        t = m.group(0)
        for name, tmpl in SITE_ATTR_RE.findall(t):
            value = html.escape(_fill(tmpl), quote=True)
            attr = re.compile(rf'(\s{name}=)"[^"]*"')
            t = attr.sub(lambda a: f'{a.group(1)}"{value}"', t, count=1) if attr.search(t) \
                else re.sub(r"\s*/?>$", lambda e: f' {name}="{value}"' + e.group(0), t, count=1)
        return t
    return SITE_TAG_RE.sub(tag, text)


def strip_generated(text: str) -> str:
    """自動生成ブロック（head）と旧クイズを取り除く。原本（src/）には置かず、build が dist/ のページにだけ入れる。"""
    return strip_quiz(HEAD_RE.sub("", text))


def apply_generated(text: str, filename: str) -> str:
    """自動生成ブロック（head）とサイト設定の差し込みを最新にし、旧クイズを取り除く（build が dist/ に書き出すページ用）。"""
    text = apply_head(apply_site(text), filename)
    return text if filename in SPECIAL_NAMES else strip_quiz(text)
