"""AI 向けの Markdown 版（dist/md/NAME.md と dist/llms.txt）の生成。"""
from __future__ import annotations

import re
from html.parser import HTMLParser

from .blocks import BACKLINK_ID, strip_quiz
from .config import CONFIG, DIST, SRC, HEAD_RE, SITE_NAME, SITE_URL, SPECIAL_NAMES, read_text

#
# build は各メモの本文を Markdown にして dist/md/NAME.md に、全メモの目次を dist/llms.txt に書き出す。
# Claude などが HTML（CSS・SVG 込みで重い）を読まずに中身を把握できるようにするため。
# 変換はファイルを触らない純粋関数（html_to_markdown）にしてあり、他の環境からも使い回せる。

MD_DIR = DIST / "md"
LLMS_TXT = DIST / "llms.txt"
MD_NOTE = "<!-- scripts/memo.py build が自動生成。手で編集しない -->"

_MD_SKIP_TAGS = {"head", "style", "script", "noscript", "template"}
_MD_SKIP_IDS = {BACKLINK_ID}
_MD_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
            "source", "track", "wbr"}
_MD_BLOCKS = {"p", "div", "section", "article", "main", "header", "footer", "nav", "aside",
              "figure", "figcaption", "blockquote", "dl", "dt", "dd", "details", "summary",
              "ul", "ol", "li", "form", "fieldset", "legend", "caption", "hr", "br", "button"}
_MD_SPACED = {"b", "strong", "small", "span", "label", "em", "i", "code", "kbd", "mark"}
_WS_RE = re.compile(r"\s+")
_MD_LIST_RE = re.compile(r"^(?:\s*(?:- |\d+\. )|\s{2,}\S)")
_MD_SCRIPT_RE = re.compile(
    r"<script\b(?![^>]*\bsrc=)(?![^>]*application/json)[^>]*>(.*?)</script>", re.S | re.I)


class _ToMarkdown(HTMLParser):
    """HTML の本文を Markdown に近いテキストにする（見た目の再現ではなく、読むための抽出）。"""

    def __init__(self, page_url: str = "") -> None:
        super().__init__(convert_charrefs=True)
        self.page_url = page_url  # 図へのリンクに使う元ページの URL（空ならリンクを付けない）
        self.anchor = ""  # いま読んでいる節の見出しの id
        self.interactive = False  # この節に操作できるパーツ（ボタンなど）があったか
        self.linked = False  # この節で図へのリンクをもう出したか
        self.blocks: list[str] = []
        self.line: list[str] = []
        self.prefix = ""
        self.cont = ""  # li の 2 行目以降に付ける字下げ
        self.skip_tag = ""
        self.skip_depth = 0
        self.lists: list[list] = []  # [種類, 番号]
        self.pre = 0
        self.pre_buf: list[str] = []
        self.links: list[tuple[int, str]] = []
        self.svg = 0
        self.svg_texts: list[str] = []
        self.svg_cur: list[str] | None = None
        self.table: list[list[str]] | None = None
        self.cell: list[str] | None = None
        self.saved_line: list[str] | None = None

    # -- 出力
    def flush(self) -> None:
        if self.cell is not None:  # 表のセルの中では改行せずに空白でつなぐ
            self.line.append(" ")
            return
        text = _WS_RE.sub(" ", "".join(self.line)).replace("****", "").strip()
        self.line = []
        if text:
            self.blocks.append(self.prefix + text)
            if self.cont:
                self.prefix = self.cont

    def emit(self, block: str) -> None:
        self.flush()
        self.blocks.append(block)

    def space(self) -> None:
        if self.line and not self.line[-1].endswith((" ", "\n")):
            self.line.append(" ")

    def here(self) -> str:
        """いまの節を元ページで開く URL。"""
        return self.page_url + (f"#{self.anchor}" if self.anchor else "")

    def close_section(self) -> None:
        """節の終わり。操作できる図解があったのに図のリンクを出していなければ案内を出す。"""
        if self.page_url and self.interactive and not self.linked:
            self.emit(f"（元のページで操作できます → {self.here()}）")
        self.interactive = self.linked = False

    # -- タグ
    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if self.skip_tag:
            if tag == self.skip_tag:
                self.skip_depth += 1
            return
        if tag in _MD_SKIP_TAGS or a.get("id") in _MD_SKIP_IDS:
            if tag not in _MD_VOID:
                self.skip_tag, self.skip_depth = tag, 1
            return
        if self.svg:
            if tag == "svg":
                self.svg += 1
            elif tag in ("text", "title") and self.svg_cur is None:
                self.svg_cur = []
            return
        if tag in ("button", "select", "textarea") or "onclick" in a or (
                tag == "input" and a.get("type") != "hidden"):
            self.interactive = True
        if tag == "svg":
            self.flush()
            self.svg, self.svg_texts = 1, []
            return
        if self.pre:
            return
        if tag == "pre":
            self.flush()
            self.pre, self.pre_buf = 1, []
        elif re.fullmatch(r"h[1-6]", tag):
            self.close_section()
            if a.get("id"):
                self.anchor = a["id"]
            elif int(tag[1]) <= 2:  # id のない大見出しはページ先頭へのリンクにする
                self.anchor = ""
            self.prefix, self.cont = "#" * int(tag[1]) + " ", ""
        elif tag == "table":
            self.flush()
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.table.append([])
        elif tag in ("td", "th") and self.table is not None:
            self.saved_line, self.line, self.cell = self.line, [], []
        elif tag in ("ul", "ol"):
            self.flush()
            self.lists.append([tag, 0])
        elif tag == "li":
            self.flush()
            depth = max(len(self.lists) - 1, 0)
            kind = self.lists[-1] if self.lists else ["ul", 0]
            kind[1] += 1
            mark = f"{kind[1]}. " if kind[0] == "ol" else "- "
            if self.cell is None:
                self.prefix = "  " * depth + mark
                self.cont = "  " * depth + " " * len(mark)
        elif tag == "img":
            if a.get("alt"):
                self.space()
                self.line.append(f"（画像: {a['alt']}）")
        elif tag == "a":
            self.space()
            self.links.append((len(self.line), a.get("href", "")))
        elif tag in _MD_BLOCKS:
            self.flush()
        elif tag in _MD_SPACED:
            self.space()
            if tag in ("b", "strong") and self.cell is None:
                self.line.append("**")
            elif tag in ("code", "kbd"):
                self.line.append("`")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _MD_VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.skip_tag:
            if tag == self.skip_tag:
                self.skip_depth -= 1
                if not self.skip_depth:
                    self.skip_tag = ""
            return
        if self.svg:
            if tag in ("text", "title") and self.svg_cur is not None:
                t = _WS_RE.sub(" ", "".join(self.svg_cur)).strip()
                if t and t not in self.svg_texts:
                    self.svg_texts.append(t)
                self.svg_cur = None
            elif tag == "svg":
                self.svg -= 1
                if not self.svg and self.svg_texts:
                    link = f" → {self.here()}" if self.page_url else ""
                    self.emit("（図: " + " / ".join(self.svg_texts) + link + "）")
                    self.linked = bool(link)
            return
        if self.pre:
            if tag == "pre":
                self.pre = 0
                code = "".join(self.pre_buf).strip("\n")
                fence = "````" if "```" in code else "```"
                self.emit(f"{fence}\n{code}\n{fence}")
            return
        if re.fullmatch(r"h[1-6]", tag):
            self.flush()
            self.prefix = self.cont = ""
        elif tag in ("td", "th") and self.cell is not None:
            text = _WS_RE.sub(" ", "".join(self.line)).strip().replace("|", "\\|")
            self.line, self.cell = self.saved_line or [], None
            if self.table is not None:
                if not self.table:
                    self.table.append([])
                self.table[-1].append(text)
        elif tag == "table" and self.table is not None:
            rows = [r for r in self.table if any(c for c in r)]
            self.table = None
            if rows:
                n = max(len(r) for r in rows)
                rows = [r + [""] * (n - len(r)) for r in rows]
                md = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * n]
                md += ["| " + " | ".join(r) + " |" for r in rows[1:]]
                self.emit("\n".join(md))
        elif tag in ("ul", "ol"):
            self.flush()
            if self.lists:
                self.lists.pop()
            if self.cell is None:
                self.prefix = self.cont = ""
        elif tag == "li":
            self.flush()
            if self.cell is None:
                self.prefix = self.cont = ""
        elif tag == "a":
            if self.links:
                start, href = self.links.pop()
                text = "".join(self.line[start:]).strip()
                url = _md_link(href)
                if url and text:
                    self.line[start:] = [f"[{text}]({url})"]
            self.space()
        elif tag in _MD_BLOCKS:
            self.flush()
        elif tag in _MD_SPACED:
            if tag in ("b", "strong") and self.cell is None:
                self.line.append("**")
            elif tag in ("code", "kbd"):
                self.line.append("`")
            self.space()

    def handle_data(self, data):
        if self.skip_tag:
            return
        if self.svg:
            if self.svg_cur is not None:
                self.svg_cur.append(data)
            return
        if self.pre:
            self.pre_buf.append(data)
            return
        self.line.append(data)

    def result(self) -> str:
        self.close()
        self.close_section()
        self.flush()
        out = ""
        for i, b in enumerate(self.blocks):  # リストの項目どうしは空行を挟まずにつなぐ
            if i:
                same_list = _MD_LIST_RE.match(b) and _MD_LIST_RE.match(self.blocks[i - 1])
                out += "\n" if same_list else "\n\n"
            out += b
        return out


def _md_link(href: str) -> str:
    """リンク先を Markdown 版から辿れる URL にする。ページ内リンクや一覧へのリンクは捨てる。"""
    if re.match(r"https?://", href):
        return href
    m = re.fullmatch(r"(?:\./)?([a-z0-9-]+)\.html(#[\w-]+)?", href)
    if m and f"{m.group(1)}.html" not in SPECIAL_NAMES:
        return f"{SITE_URL}md/{m.group(1)}.md"  # 別のメモ → その Markdown 版
    return ""


def html_to_markdown(text: str, page_url: str = "") -> str:
    """メモの HTML から本文を Markdown として取り出す（<head>・CSS・JS は除く）。

    本文の大半を JavaScript のデータから描画するページは、HTML だけでは中身が取れない。
    page_url を渡すと、図や操作できるパーツのある節に、元ページのその節へのリンクを付ける。
    取れた本文がごく短く、ページ内に大きなスクリプトがあるときは、そのスクリプトを
    （データ配列ごと）コードブロックとして末尾に付ける。"""
    text = strip_quiz(HEAD_RE.sub("", text))
    p = _ToMarkdown(page_url)
    p.feed(text)
    body = p.result()
    scripts = [s.strip() for s in _MD_SCRIPT_RE.findall(text) if s.strip()]
    if len(body) < 1000 and sum(map(len, scripts)) > 2000:
        body += "\n\n## ページ内のデータ（JavaScript で描画される部分）\n\n" + "\n\n".join(
            f"```js\n{s}\n```" for s in scripts)
    return body


def memo_markdown(text: str, meta: dict) -> str:
    """1 本のメモの Markdown 版（メタ情報＋本文）。"""
    body = html_to_markdown(text, SITE_URL + meta["file"])
    title = meta["title"]
    # 本文の先頭がページタイトルの h1 なら重複するので落とす
    body = re.sub(rf"\A#\s+{re.escape(title)}\s*(\n+|\Z)", "", body)
    head = [f"# {title}", ""]
    if meta["desc"]:
        head += [f"> {meta['desc']}", ""]
    head.append(f"- URL: {SITE_URL}{meta['file']}")
    if meta["tags"]:
        head.append(f"- タグ: {', '.join(meta['tags'])}")
    if meta["date"]:
        head.append(f"- 日付: {meta['date']}")
    return "\n".join([MD_NOTE, ""] + head + ["", "---", "", body.strip(), ""])


def llms_txt(memos: list[dict]) -> str:
    """全メモの目次（llms.txt の形式）。"""
    lines = [f"# {SITE_NAME}", ""]
    if CONFIG["llms_description"]:
        lines += [f"> {CONFIG['llms_description']}", ""]
    lines += ["## Memos", ""]
    for m in memos:
        name = m["file"][:-5]
        extra = " / ".join(x for x in (", ".join(m["tags"]), m["date"]) if x)
        line = f"- [{m['title']}]({SITE_URL}md/{name}.md)"
        if m["desc"]:
            line += f": {m['desc']}"
        if extra:
            line += f"（{extra}）"
        lines.append(line)
    return "\n".join(lines) + "\n"


def markdown_outputs(memos: list[dict]) -> dict:
    """dist/md/*.md と dist/llms.txt の中身（{書き出し先のパス: 中身}）。書き出しは build がまとめて行う。"""
    want = {MD_DIR / f"{m['file'][:-5]}.md": memo_markdown(
        read_text(SRC / m["file"]), m) for m in memos}
    want[LLMS_TXT] = llms_txt(memos)
    return want
