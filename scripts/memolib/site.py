"""サイト全体のデータ（memos.json）と、会話内プレビュー用の 1 枚の HTML。"""
from __future__ import annotations

import json
import re

from .blocks import apply_generated
from .config import DIST, SPECIAL_NAMES
from .meta import memo_files, read_meta

MEMOS_JSON = DIST / "memos.json"  # 一覧（トップページとロードマップが読む。build が dist/ に書く）


def memos_json(memos: list[dict]) -> str:
    return json.dumps(memos, ensure_ascii=False, indent=1) + "\n"


def site_data() -> list[dict]:
    return sorted((read_meta(p) for p in memo_files()),
                  key=lambda m: (m["date"], m["file"]), reverse=True)


def strip_fence(text: str) -> str:
    m = re.search(r"```(?:html)?\s*\n(.*?)\n```", text, re.S | re.I)
    return m.group(1) if m and "<" in m.group(1) else text


#
# トップページは一覧データを memos.json から読む。
# 会話内のプレビューのように HTML 1 枚しか渡せない場面のために、それを埋め込んだコピーを作る。
# 中身は公開版と同じファイルから作るので、見た目と動きは公開版と変わらない。

DATA_SCRIPT_RE = re.compile(r"<script\b", re.I)


def preview_text(text: str, filename: str) -> str:
    text = apply_generated(text, filename)
    if filename in SPECIAL_NAMES:
        data = {MEMOS_JSON.name: json.loads(memos_json(site_data()))}
        inject = ("<script>// memo.py preview が埋め込んだデータ（公開版は JSON ファイルを読み込む）\n"
                  "window.MEMO_DATA = " + json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
                  + ";\n</script>\n")
        body = re.search(r"<body\b[^>]*>", text, re.I)
        m = DATA_SCRIPT_RE.search(text, body.end() if body else 0)
        pos = m.start() if m else len(text)
        text = text[:pos] + inject + text[pos:]
    return text
