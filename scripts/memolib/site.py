"""サイト全体のデータ（memos.json・quizzes.json）と、会話内プレビュー用の 1 枚の HTML。"""
from __future__ import annotations

import json
import re
import sys

from .blocks import QUIZ_CSS, QUIZ_CSS_TAG, QUIZ_JS, QUIZ_JS_TAG, apply_generated, read_quiz, validate_quiz
from .config import DOCS, SPECIAL_NAMES, read_text
from .meta import memo_files, read_meta

MEMOS_JSON = DOCS / "memos.json"      # 一覧（トップページと quiz.html が読む）
QUIZZES_JSON = DOCS / "quizzes.json"  # 全メモの問題（ランダムクイズと quiz.html が読む）


def memos_json(memos: list[dict], quizzes: list[dict]) -> str:
    counts: dict[str, int] = {}
    for q in quizzes:
        counts[q["file"]] = counts.get(q["file"], 0) + 1
    rows = [{**m, "quizzes": counts.get(m["file"], 0)} for m in memos]
    return json.dumps(rows, ensure_ascii=False, indent=1) + "\n"


def quizzes_json(quizzes: list[dict]) -> str:
    # 1 問 1 行にして差分を読みやすくする
    if not quizzes:
        return "[]\n"
    return "[\n" + ",\n".join(json.dumps(q, ensure_ascii=False) for q in quizzes) + "\n]\n"


def site_data() -> tuple[list[dict], list[dict]]:
    memos = sorted((read_meta(p) for p in memo_files()),
                   key=lambda m: (m["date"], m["file"]), reverse=True)
    return memos, collect_quizzes(memos)


def collect_quizzes(memos: list[dict]) -> list[dict]:
    """全メモの問題を集める（形の崩れた問題は飛ばして警告）。"""
    out = []
    for m in memos:
        qs, probs = read_quiz(read_text(DOCS / m["file"]))
        if probs:
            print(f"{m['file']}: クイズに問題あり（lint で確認）: " + " / ".join(probs), file=sys.stderr)
        if not isinstance(qs, list):
            continue
        for q in qs:
            if validate_quiz([q]):
                continue
            item = {"file": m["file"], "title": m["title"], "q": q["q"],
                    "choices": q["choices"], "answer": q["answer"]}
            for k in ("explain", "ref"):
                if q.get(k):
                    item[k] = q[k]
            out.append(item)
    return out


def strip_fence(text: str) -> str:
    m = re.search(r"```(?:html)?\s*\n(.*?)\n```", text, re.S | re.I)
    return m.group(1) if m and "<" in m.group(1) else text


#
# 公開するページはクイズの CSS / JS を assets/ から、一覧データを memos.json などから読む。
# 会話内のプレビューのように HTML 1 枚しか渡せない場面のために、それらを埋め込んだコピーを作る。
# 中身は公開版と同じファイルから作るので、見た目と動きは公開版と変わらない。

DATA_SCRIPT_RE = re.compile(r"<script\b", re.I)


def _inline_tag(tag: str, body: str) -> str:
    return f"<{tag}>\n" + body.replace("</" + tag, "<\\/" + tag) + f"\n</{tag}>"


def preview_text(text: str, filename: str) -> str:
    text = apply_generated(text, filename)
    text = text.replace(QUIZ_CSS_TAG, _inline_tag("style", QUIZ_CSS.read_text(encoding="utf-8")))
    text = text.replace(QUIZ_JS_TAG, _inline_tag("script", QUIZ_JS.read_text(encoding="utf-8")))
    if filename in SPECIAL_NAMES:
        memos, quizzes = site_data()
        data = {MEMOS_JSON.name: json.loads(memos_json(memos, quizzes)),
                QUIZZES_JSON.name: quizzes}
        inject = ("<script>// memo.py preview が埋め込んだデータ（公開版は JSON ファイルを読み込む）\n"
                  "window.MEMO_DATA = " + json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
                  + ";\n</script>\n")
        body = re.search(r"<body\b[^>]*>", text, re.I)
        m = DATA_SCRIPT_RE.search(text, body.end() if body else 0)
        pos = m.start() if m else len(text)
        text = text[:pos] + inject + text[pos:]
    return text
