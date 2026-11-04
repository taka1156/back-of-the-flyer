"""各ページに差し込む自動生成ブロック（memo:head・memo:quiz）と「一覧に戻る」フッター、
確認クイズの問題データの読み取りと検証。"""
from __future__ import annotations

import html
import json
import re

from .config import (ASSETS, CONFIG, HEAD_BEGIN, HEAD_END, HEAD_RE, OG_VERSION, SITE_NAME, SITE_URL,
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


# ---------------------------------------------------------------- クイズ
#
# 各メモは問題データだけを持つ:
#   <script type="application/json" id="memo-quiz">
#   [{"q": "問題文", "choices": ["A", "B", "C"], "answer": 0,
#     "explain": "解説", "ref": "#本文の見出しなどの id"}]
#   explain / ref は任意。ref があると、間違えたときに本文の該当箇所へ飛ぶリンクが出る。
#   </script>
# 表示用の UI（<!-- memo:quiz --> ブロック）は memo.py がページ末尾に自動で入れる。
# build は全メモの問題を docs/quizzes.json に集める（トップのランダムクイズと quiz.html 用）。

QUIZ_BEGIN = "<!-- memo:quiz（scripts/memo.py が自動生成。手で編集しない） -->"
QUIZ_END = "<!-- /memo:quiz -->"
QUIZ_RE = re.compile(r"<!-- memo:quiz.*?<!-- /memo:quiz -->\n?", re.S)
QUIZ_DATA_RE = re.compile(
    r"<script\b[^>]*\bid=[\"']memo-quiz[\"'][^>]*>(.*?)</script>", re.S | re.I)

# 表示の CSS / JS は docs/assets/memo-quiz.css・memo-quiz.js に 1 つだけ置き、各メモからは参照する。
# 会話内プレビューのように HTML 1 枚しか渡せない場面では、preview コマンドが中身を埋め込む。
QUIZ_CSS = ASSETS / "memo-quiz.css"
QUIZ_JS = ASSETS / "memo-quiz.js"
QUIZ_CSS_TAG = '<link rel="stylesheet" href="assets/memo-quiz.css">'
QUIZ_JS_TAG = '<script src="assets/memo-quiz.js" defer></script>'
QUIZ_BLOCK = QUIZ_BEGIN + """
""" + QUIZ_CSS_TAG + """
<section id="memo-quiz-ui" hidden aria-labelledby="memo-quiz-title">
<h2 id="memo-quiz-title">確認クイズ <small></small></h2>
<div class="mq-list"></div>
<div class="mq-result" hidden aria-live="polite"></div>
<button type="button" class="mq-reset">やり直す</button>
</section>
""" + QUIZ_JS_TAG + """
""" + QUIZ_END + "\n"


def validate_quiz(qs) -> list[str]:
    """問題データの形をチェックし、問題点のリストを返す（空なら OK）。"""
    if not isinstance(qs, list) or not qs:
        return ["クイズは 1 問以上の配列にする"]
    probs = []
    for i, q in enumerate(qs, 1):
        if not isinstance(q, dict):
            probs.append(f"Q{i}: オブジェクトではない")
            continue
        if not isinstance(q.get("q"), str) or not q["q"].strip():
            probs.append(f"Q{i}: q（問題文）がない")
        ch = q.get("choices")
        if not (isinstance(ch, list) and 2 <= len(ch) <= 5
                and all(isinstance(c, str) and c.strip() for c in ch)):
            probs.append(f"Q{i}: choices は 2〜5 個の文字列にする")
            continue
        a = q.get("answer")
        if isinstance(a, bool) or not isinstance(a, int) or not 0 <= a < len(ch):
            probs.append(f"Q{i}: answer は choices の番号（0 始まり）にする")
        if "explain" in q and not isinstance(q["explain"], str):
            probs.append(f"Q{i}: explain は文字列にする")
        if "ref" in q and not (isinstance(q["ref"], str) and re.fullmatch(r"#[\w-]+", q["ref"])):
            probs.append(f"Q{i}: ref は \"#id\" の形にする")
    return probs


def read_quiz(text: str) -> tuple[list | None, list[str]]:
    """(問題リスト or None（データなし）, 問題点) を返す。"""
    m = QUIZ_DATA_RE.search(QUIZ_RE.sub("", text))
    if not m:
        return None, []
    try:
        qs = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        return None, [f"クイズの JSON が壊れている（{e.msg}, {e.lineno} 行目）"]
    probs = validate_quiz(qs)
    if not probs and len(qs) >= 3 and len({q["answer"] for q in qs}) == 1:
        probs.append("正解の位置（answer）が全問同じ。選択肢の順番を入れ替えて散らす")
    if not probs:
        for i, q in enumerate(qs, 1):
            ref = q.get("ref")
            if ref and not re.search(rf"\bid=[\"']?{re.escape(ref[1:])}[\"'\s>]", text):
                probs.append(f"Q{i}: ref の飛び先 {ref} がページ内にない")
    return qs, probs


def apply_quiz(text: str) -> str:
    """問題データがあれば表示用ブロックを入れる／更新する。なければ取り除く。"""
    if not QUIZ_DATA_RE.search(QUIZ_RE.sub("", text)):
        return QUIZ_RE.sub("", text)
    if QUIZ_RE.search(text):
        return QUIZ_RE.sub(lambda _: QUIZ_BLOCK, text, count=1)
    m = re.search(rf"<footer[^>]*\bid=[\"']?{BACKLINK_ID}", text)
    if not m:
        bodies = list(re.finditer(r"</body>", text, re.I))
        m = bodies[-1] if bodies else None
    pos = m.start() if m else len(text)
    return text[:pos] + QUIZ_BLOCK + text[pos:]


# ---------------------------------------------------------------- サイト設定の差し込み
#
# トップ・クイズページの「サイト名」「説明」「リポジトリへのリンク」は memo.config.json から入れる。
# ページ側では書き換えたい要素に属性で目印を付ける（値は {site_name} などを埋め込んだ書式）。
#   <h1 data-memo-site="{site_name}">…</h1>                → 要素の中身（テキスト）を置き換える
#   <a href="…" data-memo-site-href="https://…/{repository}">  → 同じタグの href 属性を置き換える
#   <meta … content="…" data-memo-site-content="{description}"> → content 属性を置き換える
# 目印の属性はそのまま残るので、何度 build しても同じ結果になる。

SITE_TEXT_RE = re.compile(r'(<([a-zA-Z][\w-]*)\b[^>]*?\sdata-memo-site="([^"]*)"[^>]*>)(.*?)(</\2\s*>)', re.S)
SITE_TAG_RE = re.compile(r'<[a-zA-Z][\w-]*\b[^>]*\sdata-memo-site-[a-z]+="[^"]*"[^>]*>')
SITE_ATTR_RE = re.compile(r'\sdata-memo-site-([a-z]+)="([^"]*)"')


def site_fields() -> dict[str, str]:
    return {"site_name": CONFIG["site_name"], "description": CONFIG["description"],
            "repository": CONFIG["repository"]}


def _fill(template: str) -> str:
    try:
        return html.unescape(template).format(**site_fields())
    except (KeyError, IndexError, ValueError) as e:
        raise SystemExit(f"data-memo-site の書式が読めない: {template!r}（使える名前: "
                         + ", ".join("{" + k + "}" for k in site_fields()) + f"）: {e}")


def apply_site(text: str) -> str:
    """data-memo-site の目印が付いた要素・属性を memo.config.json の値で置き換える。"""
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


def apply_generated(text: str, filename: str) -> str:
    """自動生成ブロック（head・クイズ）とサイト設定の差し込みをすべて最新にする。"""
    text = apply_head(apply_site(text), filename)
    return text if filename in SPECIAL_NAMES else apply_quiz(text)
