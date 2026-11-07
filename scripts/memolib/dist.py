"""build の出力（dist/）の中身を組み立てて、dist/ に書き出す。

原本（src/）は読むだけで書き換えない。dist/ は公開するサイト一式で、
src/ のファイルのコピーに、次の生成物を加えたものになる。

- 各ページ（メモ・トップ・クイズ・設定）: 自動生成ブロック（memo:head・memo:quiz）とサイト設定を差し込んだもの
- memos.json・quizzes.json（一覧と全問題。quizzes.json は memo.config.json の quiz が true のときだけ）
- md/NAME.md・llms.txt（AI 向けの Markdown 版）
- entry-skill/SKILL.md（アプリ側に置く入口スキル）

dist/ は .gitignore 済み。Actions がこの中身をそのまま dist ブランチ（memo.config.json の deploy_branch）に
コミットし、GitHub Pages はそのブランチから公開する。
"""
from __future__ import annotations

from pathlib import Path

from .blocks import QUIZ_CSS, QUIZ_JS, apply_generated
from .config import CONFIG, DIST, SRC, ENTRY_SKILL, SPECIAL_NAMES, page_enabled, read_text
from .entry import entry_skill
from .markdown import LLMS_TXT, MD_DIR, markdown_outputs
from .meta import memo_files
from .site import MEMOS_JSON, QUIZZES_JSON, memos_json, quizzes_json, site_data

# src/ にあってもコピーしないもの（どれも build が作る。昔のリポジトリの生成物が残っていても公開しない）
_GENERATED_NAMES = {MEMOS_JSON.name, QUIZZES_JSON.name, LLMS_TXT.name}
_GENERATED_DIRS = {MD_DIR.name}


def _copied_files() -> list[Path]:
    """src/ のうち、そのままコピーするファイル（ページと生成物以外）。"""
    out = []
    for p in sorted(SRC.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(SRC)
        if len(rel.parts) == 1 and (rel.suffix == ".html" or rel.name in _GENERATED_NAMES):
            continue  # ページは自動生成ブロックを入れて書き出す
        if rel.parts[0] in _GENERATED_DIRS:
            continue
        if not CONFIG["quiz"] and p in (QUIZ_CSS, QUIZ_JS):
            continue  # クイズがオフなら表示の CSS / JS も出さない
        out.append(p)
    return out


def dist_outputs() -> tuple[dict[Path, bytes], int, int]:
    """dist/ に置くべき全ファイル（{dist/ 内のパス: 中身}）と、メモの件数・問題の数。"""
    want: dict[Path, bytes] = {}
    for p in _copied_files():
        want[DIST / p.relative_to(SRC)] = p.read_bytes()
    # オプションのページ（ロードマップなど）は memo.config.json でオンのときだけ出す
    pages = memo_files() + sorted(SRC / n for n in SPECIAL_NAMES if (SRC / n).is_file() and page_enabled(n))
    for p in pages:
        want[DIST / p.name] = apply_generated(read_text(p), p.name).encode("utf-8")
    memos, quizzes = site_data()
    want[MEMOS_JSON] = memos_json(memos, quizzes).encode("utf-8")
    if CONFIG["quiz"]:  # クイズがオフなら全問題のファイルも作らない
        want[QUIZZES_JSON] = quizzes_json(quizzes).encode("utf-8")
    for path, text in markdown_outputs(memos).items():
        want[path] = text.encode("utf-8")
    want[ENTRY_SKILL] = entry_skill().encode("utf-8")
    return want, len(memos), len(quizzes)


def _existing() -> dict[Path, bytes]:
    if not DIST.is_dir():
        return {}
    return {p: p.read_bytes() for p in DIST.rglob("*") if p.is_file()}


def sync_dist(want: dict[Path, bytes], check: bool) -> tuple[list[str], list[str], list[str]]:
    """dist/ を want と同じ中身にする（check なら何も書かず、違いだけ返す）。
    返り値は (追加, 変更, 削除) のファイル名（dist/ からの相対パス）。"""
    have = _existing()
    rel = lambda p: p.relative_to(DIST).as_posix()
    added = sorted(rel(p) for p in want if p not in have)
    changed = sorted(rel(p) for p in want if p in have and have[p] != want[p])
    removed = sorted(rel(p) for p in have if p not in want)
    if check:
        return added, changed, removed
    for p, body in want.items():
        if have.get(p) != body:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)
    for name in removed:
        (DIST / name).unlink()
    # 空になったフォルダを消す（深いものから）
    for d in sorted((d for d in DIST.rglob("*") if d.is_dir()), key=lambda d: len(d.parts), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    return added, changed, removed
