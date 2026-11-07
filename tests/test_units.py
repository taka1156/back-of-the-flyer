"""memolib の関数ごとの単体テスト。

多くの関数は「文字列を受け取って文字列を返す」だけなので、ファイルを使わずに確かめる。
"""
from __future__ import annotations

import datetime as dt
import json
import unittest
from html.parser import HTMLParser

import helpers  # noqa: F401  scripts/ を import できるようにする
from memolib import blocks, config, entry, lint, markdown, meta, site


def page(head: str = "", body: str = "") -> str:
    return f"<!DOCTYPE html>\n<html><head>\n{head}</head>\n<body>\n{body}</body>\n</html>\n"


QUIZ_OK = [{"q": "Q1", "choices": ["a", "b"], "answer": 0},
           {"q": "Q2", "choices": ["a", "b", "c"], "answer": 2, "explain": "e", "ref": "#s"}]


def quiz_script(data) -> str:
    body = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f'<script type="application/json" id="memo-quiz">{body}</script>\n'


class ConfigTest(unittest.TestCase):
    def test_today_uses_configured_timezone(self):
        tz = dt.timezone(dt.timedelta(hours=config.CONFIG["utc_offset_hours"]))
        self.assertEqual(config.today(), dt.datetime.now(tz).date().isoformat())

    def test_site_url_comes_from_cname_or_repository(self):
        cname = config.SRC / "CNAME"
        if cname.is_file():
            self.assertEqual(config.SITE_URL, f"https://{cname.read_text(encoding='utf-8').strip()}/")
        else:
            self.assertEqual(config.SITE_URL, config.pages_url(config.REPOSITORY))

    def test_pages_url(self):
        self.assertEqual(config.pages_url("Alice/notes"), "https://alice.github.io/notes/")
        self.assertEqual(config.pages_url("alice/alice.github.io"), "https://alice.github.io/")
        self.assertEqual(config.pages_url(""), "")

    def test_branding_icon_style(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "memo.config.json"
            f.write_text("{}", encoding="utf-8")
            self.assertEqual(config.load_config(f)["branding"]["icon"], "mark")
            f.write_text('{"branding": {"icon": "lines"}}', encoding="utf-8")
            self.assertEqual(config.load_config(f)["branding"]["icon"], "lines")
            f.write_text('{"branding": {"icon": "bars"}}', encoding="utf-8")
            with self.assertRaises(SystemExit):
                config.load_config(f)

    def test_set_accent_rewrites_only_accent(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "memo.config.json"
            original = {"site_name": "X", "branding": {"tagline": "t", "accent": "#00d4ff", "accent_light": "#0077b6"},
                        "branch": "main"}
            f.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            cfg = config.set_accent("#3ddc97", "#0f7a50", f)
            self.assertEqual(config.accents(cfg), ("#0f7a50", "#3ddc97"))
            saved = json.loads(f.read_text(encoding="utf-8"))
            # ほかの項目と並び順はそのまま
            self.assertEqual(list(saved), ["site_name", "branding", "branch"])
            self.assertEqual(saved["branding"], {"tagline": "t", "accent": "#3ddc97", "accent_light": "#0f7a50"})
            # ライト用を空にすると項目を消し、accent から自動で決まる
            cfg = config.set_accent("#3ddc97", "", f)
            self.assertNotIn("accent_light", json.loads(f.read_text(encoding="utf-8"))["branding"])
            self.assertEqual(config.accents(cfg), (config.light_accent("#3ddc97"), "#3ddc97"))
            # 正しくない色なら止まり、ファイルは書き換える前のまま
            before = f.read_text(encoding="utf-8")
            for bad in (("green", ""), ("#3ddc97", "#12345")):
                with self.assertRaises(SystemExit):
                    config.set_accent(*bad, f)
                self.assertEqual(f.read_text(encoding="utf-8"), before)

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
            '{"roadmap": "yes"}': "roadmap は true か false",
            '{"roadmap": 1}': "roadmap は true か false",
            '{"quiz": "no"}': "quiz は true か false",
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

    def test_optional_pages_follow_config(self):
        self.assertFalse(config.page_enabled("roadmap.html", {**config.DEFAULTS}))
        self.assertTrue(config.page_enabled("roadmap.html", {**config.DEFAULTS, "roadmap": True}))
        self.assertTrue(config.page_enabled("quiz.html", {**config.DEFAULTS}))
        self.assertFalse(config.page_enabled("quiz.html", {**config.DEFAULTS, "quiz": False}))
        self.assertTrue(config.page_enabled("settings.html", {**config.DEFAULTS}))  # オプションでないページは常に出す
        self.assertTrue(set(config.OPTIONAL_PAGES) <= config.SPECIAL_NAMES)
        self.assertTrue(set(config.OPTIONAL_PAGES.values()) <= set(config.DEFAULTS))

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
        target = config.SRC / "sample.html"
        for arg in ("sample", "sample.html", "src/sample.html"):
            self.assertEqual(meta.memo_path(arg, must_exist=False), target)

    def test_memo_path_rejects_reserved_and_bad_names(self):
        for arg in ("index", "quiz.html", "Bad_Name"):
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


class QuizTest(unittest.TestCase):
    def setUp(self):
        # クイズの表示・プレビューを確かめるので、リポジトリの設定（quiz が false のサイトもある）に関わらずオンにする
        orig = config.CONFIG["quiz"]
        config.CONFIG["quiz"] = True
        self.addCleanup(config.CONFIG.__setitem__, "quiz", orig)

    def test_validate_accepts_good_data(self):
        self.assertEqual(blocks.validate_quiz(QUIZ_OK), [])

    def test_validate_reports_each_problem(self):
        bad = [
            {"choices": ["a", "b"], "answer": 0},                      # q がない
            {"q": "Q", "choices": ["a"], "answer": 0},                  # 選択肢が 1 個
            {"q": "Q", "choices": ["a", "b"], "answer": 2},             # 範囲外
            {"q": "Q", "choices": ["a", "b"], "answer": True},          # bool は番号ではない
            {"q": "Q", "choices": ["a", "b"], "answer": 0, "ref": "s"},  # # がない
            "文字列",
        ]
        probs = blocks.validate_quiz(bad)
        for i in range(1, len(bad) + 1):
            self.assertTrue(any(p.startswith(f"Q{i}:") for p in probs), (i, probs))
        self.assertTrue(blocks.validate_quiz([]))

    def test_read_quiz_checks_json_refs_and_answer_spread(self):
        qs, probs = blocks.read_quiz(page(body='<h2 id="s">S</h2>' + quiz_script(QUIZ_OK)))
        self.assertEqual((qs, probs), (QUIZ_OK, []))

        _, probs = blocks.read_quiz(page(body=quiz_script(QUIZ_OK)))  # #s がページにない
        self.assertTrue(any("#s" in p for p in probs))

        _, probs = blocks.read_quiz(page(body=quiz_script("[{broken")))
        self.assertTrue(any("JSON" in p for p in probs))

        same = [{"q": f"Q{i}", "choices": ["a", "b"], "answer": 1} for i in range(3)]
        _, probs = blocks.read_quiz(page(body=quiz_script(same)))
        self.assertTrue(any("answer" in p for p in probs))

        self.assertEqual(blocks.read_quiz(page(body="<p>なし</p>")), (None, []))

    def test_strip_generated_undoes_apply_generated(self):
        text = ("<!DOCTYPE html><html><head><title>T</title></head><body><h2 id=\"s\">S</h2>"
                '<script type="application/json" id="memo-quiz">'
                '[{"q":"Q","choices":["a","b"],"answer":1}]</script></body></html>')
        done = blocks.apply_generated(text, "t.html")
        self.assertIn(blocks.QUIZ_BEGIN, done)
        self.assertEqual(blocks.strip_generated(done), text)

    def test_apply_quiz_inserts_before_footer_once_and_removes_when_no_data(self):
        text = page(body="<p>本文</p>\n" + blocks.BACKLINK + "\n" + quiz_script(QUIZ_OK))
        once = blocks.apply_quiz(text)
        self.assertEqual(blocks.apply_quiz(once), once)
        self.assertEqual(once.count(blocks.QUIZ_BEGIN), 1)
        self.assertLess(once.index(blocks.QUIZ_BEGIN), once.index(blocks.BACKLINK_ID))
        self.assertIn(blocks.QUIZ_JS_TAG, once)
        without = once.replace(quiz_script(QUIZ_OK), "")
        self.assertNotIn(blocks.QUIZ_BEGIN, blocks.apply_quiz(without))

    def test_special_pages_get_no_quiz_block(self):
        text = page("<title>T</title>", quiz_script(QUIZ_OK))
        self.assertNotIn(blocks.QUIZ_BEGIN, blocks.apply_generated(text, "index.html"))
        self.assertIn(blocks.QUIZ_BEGIN, blocks.apply_generated(text, "memo.html"))

    def test_quiz_assets_exist(self):
        self.assertTrue(blocks.QUIZ_CSS.is_file())
        self.assertTrue(blocks.QUIZ_JS.is_file())


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
""" + blocks.BACKLINK + quiz_script([{"q": "秘密の問題", "choices": ["a", "b"], "answer": 0}]))

    def test_converts_body(self):
        md = markdown.html_to_markdown(blocks.apply_quiz(self.HTML), "https://ex.com/p.html")
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


class _TagCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.starts: dict[str, int] = {}

    def handle_starttag(self, tag, attrs):
        self.starts[tag] = self.starts.get(tag, 0) + 1


class SiteTest(unittest.TestCase):
    def setUp(self):
        # クイズの表示・プレビューを確かめるので、リポジトリの設定（quiz が false のサイトもある）に関わらずオンにする
        orig = config.CONFIG["quiz"]
        config.CONFIG["quiz"] = True
        self.addCleanup(config.CONFIG.__setitem__, "quiz", orig)

    def test_json_writers(self):
        memos = [{"file": "a.html", "title": "A", "desc": "", "tags": [], "date": "2026-01-01"},
                 {"file": "b.html", "title": "B", "desc": "", "tags": [], "date": "2026-01-01"}]
        quizzes = [{"file": "a.html", "q": "Q"}, {"file": "a.html", "q": "Q2"}]
        rows = json.loads(site.memos_json(memos, quizzes))
        self.assertEqual([r["quizzes"] for r in rows], [2, 0])
        self.assertEqual(json.loads(site.quizzes_json(quizzes)), quizzes)
        self.assertEqual(site.quizzes_json([]), "[]\n")
        self.assertEqual(site.quizzes_json(quizzes).count("\n"), 4, "1 問 1 行")

    def test_strip_fence(self):
        self.assertEqual(site.strip_fence("```html\n<p>x</p>\n```"), "<p>x</p>")
        self.assertEqual(site.strip_fence("<p>x</p>"), "<p>x</p>")
        self.assertEqual(site.strip_fence("```\nnot html\n```"), "```\nnot html\n```")

    def test_preview_inlines_assets_and_escapes_closing_tags(self):
        text = page("<title>T</title>", '<h2 id="s">S</h2>' + quiz_script(QUIZ_OK))
        out = site.preview_text(text, "t.html")
        self.assertNotIn(blocks.QUIZ_CSS_TAG, out)
        self.assertNotIn(blocks.QUIZ_JS_TAG, out)
        # ブラウザと同じく <script> の中身は解釈せずに数える。埋め込んだ JS が途中でタグを閉じていれば数が増える
        counter = _TagCounter()
        counter.feed(out)
        self.assertEqual(counter.starts.get("script"), 2)  # 埋め込んだクイズの JS と問題データ
        self.assertIn(blocks.QUIZ_JS.read_text(encoding="utf-8").strip()[:40], out)

    def test_inline_tag_escapes_its_closing_tag(self):
        self.assertEqual(site._inline_tag("script", "a</script>b"), "<script>\na<\\/script>b\n</script>")

    @unittest.skipUnless(helpers.repo_has_memos() and config.load_config()["quiz"],
                         "本物のメモがない（仕組みだけのリポジトリ）か、クイズを使わないサイト")
    def test_collect_quizzes_from_repository_are_valid(self):
        qs = site.collect_quizzes(site.site_data()[0])
        self.assertTrue(qs)
        self.assertEqual(blocks.validate_quiz(qs and [{k: q[k] for k in ("q", "choices", "answer")} for q in qs]), [])


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

    def test_optional_elements_are_removed_only_when_off(self):
        src = ('<footer>\n    <a href="a.html">A</a>\n'
               '    <span data-memo-if="roadmap">· <a href="roadmap.html">ロードマップ</a></span>\n'
               '    · <a href="settings.html">設定</a>\n</footer>')
        orig = dict(blocks.CONFIG)
        try:
            blocks.CONFIG["roadmap"] = False
            out = blocks.apply_site(src)
            self.assertEqual(out, '<footer>\n    <a href="a.html">A</a>\n    · <a href="settings.html">設定</a>\n</footer>')
            self.assertEqual(blocks.apply_site(out), out)
            blocks.CONFIG["roadmap"] = True
            self.assertEqual(blocks.apply_site(src), src)  # オンなら何も変えない
            with self.assertRaises(SystemExit):
                blocks.apply_site('<span data-memo-if="nope">x</span>')
        finally:
            blocks.CONFIG.clear()
            blocks.CONFIG.update(orig)

    def test_unknown_field_is_an_error(self):
        with self.assertRaises(SystemExit):
            blocks.apply_site('<h1 data-memo-site="{nope}">x</h1>')


if __name__ == "__main__":
    unittest.main()
