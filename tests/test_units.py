"""memolib の関数ごとの単体テスト。

多くの関数は「文字列を受け取って文字列を返す」だけなので、ファイルを使わずに確かめる。
"""
from __future__ import annotations

import datetime as dt
import json
import unittest

import helpers  # noqa: F401  scripts/ を import できるようにする
from memolib import blocks, config, entry, lint, markdown, meta, site


def page(head: str = "", body: str = "") -> str:
    return f"<!DOCTYPE html>\n<html><head>\n{head}</head>\n<body>\n{body}</body>\n</html>\n"


# 廃止した確認クイズの名残（以前のメモに残っている表示ブロックと問題データ）
LEGACY_QUIZ = ("<!-- memo:quiz（scripts/memo.py が自動生成。手で編集しない） -->\n"
               '<link rel="stylesheet" href="assets/memo-quiz.css">\n'
               '<section id="memo-quiz-ui" hidden><h2>確認クイズ</h2></section>\n'
               "<!-- /memo:quiz -->\n"
               '<script type="application/json" id="memo-quiz">'
               '[{"q": "秘密の問題", "choices": ["a", "b"], "answer": 0}]</script>\n')


class ConfigTest(unittest.TestCase):
    def test_today_uses_configured_timezone(self):
        tz = dt.timezone(dt.timedelta(hours=config.CONFIG["utc_offset_hours"]))
        self.assertEqual(config.today(), dt.datetime.now(tz).date().isoformat())

    def test_site_url_comes_from_cname_or_repository(self):
        cname = config.DOCS / "CNAME"
        if cname.is_file():
            self.assertEqual(config.SITE_URL, f"https://{cname.read_text(encoding='utf-8').strip()}/")
        else:
            self.assertEqual(config.SITE_URL, config.pages_url(config.REPOSITORY))

    def test_pages_url(self):
        self.assertEqual(config.pages_url("Alice/notes"), "https://alice.github.io/notes/")
        self.assertEqual(config.pages_url("alice/alice.github.io"), "https://alice.github.io/")
        self.assertEqual(config.pages_url(""), "")

    def test_load_config_fills_defaults_and_rejects_unknown_keys(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "memo.config.json"
            # ファイルがなくても既定値で動く（branding の中も既定値で埋まる）
            self.assertEqual(config.load_config(f), {**config.DEFAULTS, "branding": config.BRANDING_DEFAULTS})
            f.write_text('{"site_name": "X"}', encoding="utf-8")
            self.assertEqual(config.load_config(f)["site_name"], "X")
            self.assertEqual(config.load_config(f)["branch"], config.DEFAULTS["branch"])
            f.write_text('{"sitename": "X"}', encoding="utf-8")
            with self.assertRaises(SystemExit):
                config.load_config(f)

    def test_load_config_reports_mistakes_without_traceback(self):
        import tempfile
        from pathlib import Path
        cases = {
            '{"site_name": "x",}': "JSON の書き方",
            '[1, 2]': "全体を",
            '{"utc_offset_hours": "9"}': "utc_offset_hours は数値",
            '{"utc_offset_hours": true}': "utc_offset_hours は数値",
            '{"utc_offset_hours": 24}': "-24 より大きく",
            '{"site_name": 123}': "site_name は文字列",
            '{"site_name": "  "}': "site_name を空にはできません",
            '{"branch": ""}': "branch を空にはできません",
            '{"branch": "my branch"}': "branch に空白",
            '{"repository": null}': "repository は文字列",
            '{"branding": {"mark": 1}}': "branding.mark は文字列",
            '{"sitename": "x"}': "使える項目",
        }
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "memo.config.json"
            for text, expected in cases.items():
                f.write_text(text, encoding="utf-8")
                with self.assertRaises(SystemExit, msg=text) as cm:
                    config.load_config(f)
                self.assertIn(expected, str(cm.exception), text)
                self.assertTrue(str(cm.exception).startswith("memo.config.json: "), text)
            f.write_bytes('{"site_name": "テスト"}'.encode("shift_jis"))
            with self.assertRaises(SystemExit) as cm:
                config.load_config(f)
            self.assertIn("UTF-8", str(cm.exception))
            f.write_text('{"utc_offset_hours": -3.5, "branch": "trunk"}', encoding="utf-8")
            self.assertEqual(config.load_config(f)["utc_offset_hours"], -3.5)  # 小数・負の数は使える

    def test_read_text_reports_non_utf8_file(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.html"
            f.write_bytes("<title>テスト</title>".encode("shift_jis"))
            with self.assertRaises(SystemExit) as cm:
                config.read_text(f)
            self.assertIn("UTF-8 で読めません", str(cm.exception))
            self.assertIn("x.html", str(cm.exception))

    def test_branding_is_validated_and_filled_from_site_settings(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "memo.config.json"
            for bad in ('{"branding": {"color": "#fff"}}', '{"branding": {"accent": "blue"}}',
                        '{"branding": {"accent_light": "#12"}}',
                        '{"branding": {"theme": "pink"}}', '{"branding": "x"}'):
                f.write_text(bad, encoding="utf-8")
                with self.assertRaises(SystemExit, msg=bad):
                    config.load_config(f)
            f.write_text('{"site_name": "notes", "description": "D", "branding": {"accent": "#abc"}}', encoding="utf-8")
            b = config.branding(config.load_config(f), "https://alice.github.io/notes/")
            self.assertEqual((b["title"], b["tagline"], b["url"], b["mark"], b["accent"], b["theme"]),
                             ("notes", "D", "alice.github.io/notes", "N", "#aabbcc", "dark"))
            f.write_text('{"branding": {"title": "T", "tagline": "G", "url": "x.dev", "mark": "MK"}}', encoding="utf-8")
            b = config.branding(config.load_config(f), "https://ignored/")
            self.assertEqual((b["title"], b["tagline"], b["url"], b["mark"]), ("T", "G", "x.dev", "MK"))

    def test_accents_for_light_and_dark_mode(self):
        cfg = lambda **b: {"branding": {**config.BRANDING_DEFAULTS, **b}}  # noqa: E731
        self.assertEqual(config.accents(cfg(accent="#ABC", accent_light="#123")), ("#112233", "#aabbcc"))
        light, dark = config.accents(cfg(accent="#00d4ff"))  # accent_light が空なら白地で読める濃さに
        self.assertEqual(dark, "#00d4ff")
        self.assertGreaterEqual(config.contrast_on_white(light), 4.5)
        self.assertLess(config.contrast_on_white(light), 5.0)  # 必要以上に暗くしない
        self.assertEqual(config.accents(cfg(accent="#000000"))[0], "#000000")  # もともと読める色はそのまま

    def test_repository_warning(self):
        self.assertEqual(config.repository_warning("alice/notes"), "")
        for bad in ("", "  ", "notes", "a/b/c", "/notes", "repo/sample", "OWNER/REPO"):
            self.assertIn("repository", config.repository_warning(bad), bad)

    def test_entry_skill_name_follows_skill_name_rule(self):
        self.assertEqual(entry.skill_name("alice/notes"), "notes")
        self.assertEqual(entry.skill_name("Alice/My.Notes"), "my-notes")
        self.assertEqual(entry.skill_name("alice/alice.github.io"), "alice-github-io")
        self.assertEqual(entry.skill_name("a/__x__y--z__"), "x-y-z")
        self.assertEqual(entry.skill_name("a/..."), "memo")  # 何も残らなければ既定の名前
        self.assertEqual(entry.skill_name("a/" + "x" * 80), "x" * entry.SKILL_NAME_MAX)
        self.assertRegex(entry.skill_name("a/" + "x" * 63 + ".y"), r"^[a-z0-9]+(-[a-z0-9]+)*$")

    def test_name_rule(self):
        for ok in ("docker", "git-rebase", "a1-b2"):
            self.assertRegex(ok, config.NAME_RE)
        for ng in ("Docker", "a_b", "a--b", "-a", "a-", ""):
            self.assertNotRegex(ng, config.NAME_RE)


class MetaTest(unittest.TestCase):
    def test_parse_meta_ignores_generated_head_block(self):
        text = page('<title>本物</title>\n<meta name="description" content="説明">\n'
                    + blocks.head_block(page("<title>古い</title>"), "x.html"))
        m, title = meta.parse_meta(text)
        self.assertEqual(title, "本物")
        self.assertEqual(m["description"], "説明")

    def test_set_meta_replaces_or_inserts_and_escapes(self):
        text = page('<title>T</title>\n<meta name="memo:tags" content="old">\n')
        text = meta.set_meta(text, "memo:tags", "a, b")
        text = meta.set_meta(text, "description", 'x "y" <z>')
        self.assertEqual(text.count('name="memo:tags"'), 1)
        self.assertIn('<meta name="memo:tags" content="a, b">', text)
        self.assertIn('<meta name="description" content="x &quot;y&quot; &lt;z&gt;">', text)
        self.assertLess(text.index('name="description"'), text.index("</head>"))

    def test_memo_path_resolves_names(self):
        target = config.DOCS / "sample.html"
        for arg in ("sample", "sample.html", "docs/sample.html"):
            self.assertEqual(meta.memo_path(arg, must_exist=False), target)

    def test_memo_path_rejects_reserved_and_bad_names(self):
        for arg in ("index", "index.html", "Bad_Name"):
            with self.assertRaises(SystemExit):
                meta.memo_path(arg, must_exist=False)

    def test_memo_files_excludes_special_pages(self):
        names = {p.name for p in meta.memo_files()}  # 仕組みだけのリポジトリでは空でもよい
        self.assertFalse(names & config.SPECIAL_NAMES)


class HeadBlockTest(unittest.TestCase):
    def test_head_block_uses_title_and_description(self):
        b = blocks.head_block(page('<title>A &amp; B</title><meta name="description" content="説明">'), "foo.html")
        self.assertIn('<meta property="og:title" content="A &amp; B">', b)
        self.assertIn('<meta property="og:description" content="説明">', b)
        self.assertIn(f'<meta property="og:url" content="{config.SITE_URL}foo.html">', b)
        self.assertIn('content="article"', b)
        self.assertIn('content="website"', blocks.head_block(page("<title>x</title>"), "index.html"))

    def test_head_block_sets_accent_for_both_color_schemes(self):
        light, dark = config.accents()
        block = blocks.head_block(page("<title>T</title>"), "x.html")
        self.assertIn(f"html:root{{--accent:{light}}}", block)
        self.assertIn(f"@media (prefers-color-scheme: dark){{html:root{{--accent:{dark}}}}}", block)

    def test_apply_head_is_idempotent_and_single(self):
        text = page("<title>T</title>")
        once = blocks.apply_head(text, "t.html")
        self.assertEqual(blocks.apply_head(once, "t.html"), once)
        self.assertEqual(once.count(config.HEAD_BEGIN), 1)
        self.assertLess(once.index(config.HEAD_BEGIN), once.index("</head>"))


class LegacyQuizTest(unittest.TestCase):
    def test_strip_quiz_removes_block_and_data(self):
        text = page("<title>T</title>", "<p>本文</p>\n" + LEGACY_QUIZ + blocks.BACKLINK + "\n")
        stripped = blocks.strip_quiz(text)
        self.assertEqual(stripped, page("<title>T</title>", "<p>本文</p>\n" + blocks.BACKLINK + "\n"))
        self.assertEqual(blocks.strip_quiz(stripped), stripped)

    def test_apply_generated_strips_quiz_from_memos(self):
        text = page("<title>T</title>", LEGACY_QUIZ)
        self.assertNotIn("memo-quiz", blocks.apply_generated(text, "memo.html"))

    def test_lint_fix_reports_removal(self):
        text = page("<title>T</title>", LEGACY_QUIZ)
        fixed, notes, _ = lint.lint_text(text, backlink=False, filename="memo.html")
        self.assertNotIn("memo-quiz", fixed)
        self.assertTrue(any("クイズ" in n for n in notes))
        self.assertFalse(any("クイズ" in n for n in lint.lint_text(fixed, False, "memo.html")[1]))


class LintTest(unittest.TestCase):
    def test_fixes_broken_css(self):
        text = page("<title>T</title><style>\n- { margin: 0 }\n\\* { padding: 0 }\n"
                    "body { font-family: ‘Noto’, “X” }\n</style>")
        fixed, notes, _ = lint.lint_text(text, backlink=False)
        self.assertIn("* { margin: 0 }", fixed)
        self.assertIn("\n* { padding: 0 }", fixed)
        self.assertIn("font-family: 'Noto', \"X\"", fixed)
        self.assertEqual(len([n for n in notes if "CSS" in n]), 3)

    def test_adds_doctype_charset_viewport_and_backlink(self):
        fixed, notes, _ = lint.lint_text("<html><head><title>T</title></head><body></body></html>", backlink=True)
        self.assertTrue(fixed.startswith("<!DOCTYPE html>"))
        self.assertIn('<meta charset="UTF-8">', fixed)
        self.assertIn('name="viewport"', fixed)
        self.assertIn(blocks.BACKLINK_ID, fixed)
        self.assertEqual(lint.lint_text(fixed, backlink=True)[1], [])  # 2 回目は直すものがない

    def test_reports_missing_meta_and_curly_quotes_in_js(self):
        text = page("<title>T</title>", "<script>const a = “x”;</script>")
        _, _, probs = lint.lint_text(text, backlink=False)
        joined = " / ".join(probs)
        for word in ("説明", "タグ", "日付", "全角クォート", "index.html"):
            self.assertIn(word, joined)


class MarkdownTest(unittest.TestCase):
    HTML = page("<title>T</title><style>.a{}</style>", """
<h2 id="s1">見出し</h2>
<p>本文 <b>強調</b> と <code>c</code>。<a href="docker.html#x">別メモ</a> <a href="index.html">一覧</a> <a href="https://e.com">外</a></p>
<ul><li>一</li><li>二</li></ul>
<svg><text>ラベルA</text><text>ラベルB</text></svg>
<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>
<pre>code
  line</pre>
""" + blocks.BACKLINK + LEGACY_QUIZ)

    def test_converts_body(self):
        md = markdown.html_to_markdown(self.HTML, "https://ex.com/p.html")
        self.assertIn("## 見出し", md)
        self.assertIn("**強調**", md)
        self.assertIn("`c`", md)
        self.assertIn(f"[別メモ]({config.SITE_URL}md/docker.md)", md)
        self.assertIn("[外](https://e.com)", md)
        self.assertNotIn("](index.html", md)
        self.assertIn("- 一\n- 二", md)
        self.assertIn("（図: ラベルA / ラベルB → https://ex.com/p.html#s1）", md)
        self.assertIn("| A | B |\n| --- | --- |\n| 1 | 2 |", md)
        self.assertIn("```\ncode\n  line\n```", md)
        for hidden in (".a{}", "秘密の問題", "確認クイズ", "一覧に戻る"):
            self.assertNotIn(hidden, md)

    def test_memo_markdown_has_header_and_no_duplicate_title(self):
        m = {"file": "p.html", "title": "見出し", "desc": "説明", "tags": ["a"], "date": "2026-01-01"}
        md = markdown.memo_markdown(page(body="<h1>見出し</h1><p>本文</p>"), m)
        self.assertTrue(md.startswith(markdown.MD_NOTE))
        self.assertEqual(md.count("# 見出し"), 1)
        for line in ("> 説明", f"- URL: {config.SITE_URL}p.html", "- タグ: a", "- 日付: 2026-01-01"):
            self.assertIn(line, md)

    def test_llms_txt_lists_markdown_links(self):
        txt = markdown.llms_txt([{"file": "p.html", "title": "T", "desc": "D", "tags": ["a", "b"], "date": "2026-01-01"}])
        self.assertIn(f"- [T]({config.SITE_URL}md/p.md): D（a, b / 2026-01-01）", txt)


class SiteTest(unittest.TestCase):
    def test_json_writers(self):
        memos = [{"file": "a.html", "title": "A", "desc": "", "tags": [], "date": "2026-01-01"},
                 {"file": "b.html", "title": "B", "desc": "", "tags": [], "date": "2026-01-01"}]
        self.assertEqual(json.loads(site.memos_json(memos)), memos)

    def test_strip_fence(self):
        self.assertEqual(site.strip_fence("```html\n<p>x</p>\n```"), "<p>x</p>")
        self.assertEqual(site.strip_fence("<p>x</p>"), "<p>x</p>")
        self.assertEqual(site.strip_fence("```\nnot html\n```"), "```\nnot html\n```")

    def test_memo_preview_is_the_generated_page(self):
        text = page("<title>T</title>", "<p>本文</p>")
        self.assertEqual(site.preview_text(text, "t.html"), blocks.apply_generated(text, "t.html"))


class SiteFieldsTest(unittest.TestCase):
    def fields(self):
        return blocks.site_fields()

    def test_text_and_attributes_are_filled(self):
        f = self.fields()
        src = ('<title data-memo-site="{site_name} クイズ">古い</title>\n'
               '<meta name="description" content="古い" data-memo-site-content="{description}">\n'
               '<a href="x" data-memo-site="github.com/{repository}" data-memo-site-href="https://github.com/{repository}">古い</a>\n'
               '<p>そのまま</p>')
        out = blocks.apply_site(src)
        self.assertIn(f'>{f["site_name"]} クイズ</title>', out)
        self.assertIn(f'content="{f["description"]}" data-memo-site-content="{{description}}"', out)
        self.assertIn(f'<a href="https://github.com/{f["repository"]}"', out)
        self.assertIn(f'>github.com/{f["repository"]}</a>', out)
        self.assertIn("<p>そのまま</p>", out)
        self.assertEqual(blocks.apply_site(out), out)  # 何度やっても同じ

    def test_missing_attribute_is_added(self):
        out = blocks.apply_site('<a data-memo-site-href="https://github.com/{repository}">x</a>')
        self.assertIn(f'href="https://github.com/{self.fields()["repository"]}"', out)

    def test_values_are_escaped(self):
        orig = dict(blocks.CONFIG)
        try:
            blocks.CONFIG["site_name"] = 'A & "B" <C>'
            out = blocks.apply_site('<h1 data-memo-site="{site_name}">x</h1><meta content="" data-memo-site-content="{site_name}">')
            self.assertIn('>A &amp; "B" &lt;C&gt;</h1>', out)
            self.assertIn('content="A &amp; &quot;B&quot; &lt;C&gt;"', out)
        finally:
            blocks.CONFIG.clear()
            blocks.CONFIG.update(orig)

    def test_unknown_field_is_an_error(self):
        with self.assertRaises(SystemExit):
            blocks.apply_site('<h1 data-memo-site="{nope}">x</h1>')


if __name__ == "__main__":
    unittest.main()
