"""メモの <head> のメタ情報（タイトル・説明・タグ・日付）の読み書きと、メモの場所の解決。"""
from __future__ import annotations

import html
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

from .config import DOCS, HEAD_RE, NAME_RE, ROOT, SPECIAL_NAMES, read_text

class _Meta(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title" and not self.title:
            self._in_title = True
        elif tag == "meta" and "name" in a:
            self.meta.setdefault(a["name"].lower(), a.get("content", ""))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def parse_meta(text: str) -> tuple[dict, str]:
    p = _Meta()
    p.feed(HEAD_RE.sub("", text))
    return p.meta, p.title.strip()


def read_meta(path: Path) -> dict:
    p = _Meta()
    p.feed(HEAD_RE.sub("", read_text(path)))
    m = p.meta
    tags = [t.strip() for t in m.get("memo:tags", "").split(",") if t.strip()]
    return {
        "file": path.name,
        "title": (m.get("memo:title") or p.title).strip() or path.stem,
        "desc": m.get("description", "").strip(),
        "tags": tags,
        "date": m.get("memo:date", "").strip() or git_added_date(path),
    }


def git_added_date(path: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--follow", "--format=%cs", "--",
             str(path.resolve().relative_to(ROOT))],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.split()
        return out[-1] if out else ""
    except Exception:
        return ""


def memo_path(arg: str, must_exist: bool = True) -> Path:
    """名前やパスを docs/ 内のメモのパスに解決する。"""
    p = Path(arg)
    if p.is_file():
        return p.resolve()
    name = p.name[:-5] if p.name.endswith(".html") else p.name
    if not NAME_RE.match(name):
        sys.exit(f"ファイル名は英小文字・数字・ハイフンのみ: {name!r}")
    if f"{name}.html" in SPECIAL_NAMES:
        sys.exit(f"{name}.html は特別なページです（トップ）。メモ名に使えません")
    target = DOCS / f"{name}.html"
    if must_exist and not target.is_file():
        sys.exit(f"見つかりません: {target.relative_to(ROOT)}")
    return target


def memo_files() -> list[Path]:
    return sorted(p for p in DOCS.glob("*.html") if p.name not in SPECIAL_NAMES)


def set_meta(text: str, name: str, value: str) -> str:
    tag = f'<meta name="{name}" content="{html.escape(value, quote=True)}">'
    pat = re.compile(rf"<meta[^>]+name=[\"']?{re.escape(name)}[\"'\s][^>]*>", re.I)
    if pat.search(text):
        return pat.sub(lambda _: tag, text, count=1)
    m = re.search(r"</head>", text, re.I)
    if m:
        return text[: m.start()] + tag + "\n" + text[m.start():]
    m = re.search(r"<title>.*?</title>", text, re.I | re.S)
    if m:
        return text[: m.end()] + "\n" + tag + text[m.end():]
    m = re.search(r"<html[^>]*>", text, re.I)
    pos = m.end() if m else 0
    return text[:pos] + "\n" + tag + text[pos:]
