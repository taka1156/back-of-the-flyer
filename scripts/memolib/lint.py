"""崩れのチェックと自動修正（lint）。"""
from __future__ import annotations

import re

from .blocks import BACKLINK, BACKLINK_ID, apply_head, apply_quiz, read_quiz

CURLY = "‘’“”"


STYLE_RE = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.S | re.I)
SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)


def _fix_css(css: str) -> tuple[str, list[str]]:
    notes = []
    n = sum(css.count(c) for c in CURLY)
    if n:
        css = css.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
        notes.append(f"CSS 内の全角クォート {n} 個を半角に修正")
    css2, k = re.subn(r"(^|\n)([ \t]*)- \{", r"\1\2* {", css)
    if k:
        css = css2
        notes.append("CSS の `- {`（`* {` の化け）を修正")
    css2, k = re.subn(r"(^|\n)([ \t]*)\\\*", r"\1\2*", css)
    if k:
        css = css2
        notes.append("CSS の `\\*`（エスケープ化け）を修正")
    return css, notes


def lint_text(text: str, backlink: bool, filename: str = "") -> tuple[str, list[str], list[str]]:
    """returns (fixed_text, fixed_notes, problems_remaining)"""
    fixed: list[str] = []
    problems: list[str] = []

    # CSS の化け
    def repl(m):
        css, notes = _fix_css(m.group(2))
        fixed.extend(notes)
        return m.group(1) + css + m.group(3)
    text = STYLE_RE.sub(repl, text)

    # JS 内の全角クォート（文字列内の正当な使用もあり得るので警告のみ）
    for js in SCRIPT_RE.findall(text):
        if re.search(r"[=(,:\[]\s*[‘“]", js):
            problems.append("JS 内で全角クォートが文字列の区切りに使われている疑い（手動確認）")
            break

    low = text.lower()
    if not low.lstrip().startswith("<!doctype"):
        text = "<!DOCTYPE html>\n" + text
        fixed.append("<!DOCTYPE html> を追加")

    def ensure_head(snippet: str, test: str, label: str):
        nonlocal text
        if re.search(test, text, re.I):
            return
        m = re.search(r"<head[^>]*>", text, re.I)
        if m:
            text = text[: m.end()] + "\n" + snippet + text[m.end():]
        else:
            m = re.search(r"<html[^>]*>", text, re.I)
            pos = m.end() if m else text.find("\n") + 1
            text = text[:pos] + "\n" + snippet + text[pos:]
        fixed.append(f"{label} を追加")

    ensure_head('<meta charset="UTF-8">', r"<meta[^>]+charset", "charset")
    ensure_head('<meta name="viewport" content="width=device-width, initial-scale=1.0">',
                r"<meta[^>]+name=[\"']?viewport", "viewport")

    if not re.search(r"<title>\s*\S", text, re.I):
        problems.append("<title> がない（memo.py meta --title で追加）")
    for name, label in (("description", "説明"), ("memo:tags", "タグ"), ("memo:date", "日付")):
        if not re.search(rf"<meta[^>]+name=[\"']?{re.escape(name)}[\"'\s]", text, re.I):
            problems.append(f"{label}（meta {name}）がない（memo.py meta で追加）")

    if backlink and BACKLINK_ID not in text:
        m = list(re.finditer(r"</body>", text, re.I))
        if m:
            i = m[-1].start()
            text = text[:i] + BACKLINK + "\n" + text[i:]
        else:
            text = text.rstrip() + "\n" + BACKLINK + "\n"
        fixed.append("フッターに「一覧に戻る」リンクを追加")
    elif BACKLINK_ID not in text and "index.html" not in text:
        problems.append("一覧（index.html）へのリンクがない（--backlink で追加）")

    if filename:
        new = apply_head(text, filename)
        if new != text:
            fixed.append("アイコン・OGP の head タグを追加／更新")
            text = new
        new = apply_quiz(text)
        if new != text:
            fixed.append("クイズの表示ブロック（memo:quiz）を追加／更新")
            text = new

    _qs, quiz_problems = read_quiz(text)
    problems.extend(f"クイズ: {p}" for p in quiz_problems)

    return text, fixed, problems
