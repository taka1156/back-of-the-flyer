"""memo.py をコマンドとして外から動かす結合テスト。

中身の作りを変えても（リファクタリングしても）通るように、コマンドの入出力と
生成されるファイルだけを見る。

ほとんどのテストは tests/fixtures/ のサンプルのメモで動く（本物のメモがなくても通る）。
RepositoryTest だけはこのリポジトリの本物のメモを確かめ、メモが 1 本もなければ飛ばす。
"""
from __future__ import annotations

import json
import re
import unittest

from helpers import ENTRY_REL, REPO, Workspace, diff_names, repo_has_memos, repo_snapshot

GENERATED_BLOCKS = (r"<!-- memo:head.*?<!-- /memo:head -->\n?", r"<!-- memo:quiz.*?<!-- /memo:quiz -->\n?")


def strip_generated(ws: Workspace) -> None:
    """自動生成ブロックと生成物をすべて消す（原本だけの状態にする）。"""
    for page in ws.docs.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        for pat in GENERATED_BLOCKS:
            text = re.sub(pat, "", text, flags=re.S)
        page.write_text(text, encoding="utf-8")
    for name in ("memos.json", "quizzes.json", "llms.txt"):
        (ws.docs / name).unlink()
    for md in (ws.docs / "md").glob("*.md"):
        md.unlink()
    (ws.root / ENTRY_REL).unlink(missing_ok=True)


@unittest.skipUnless(repo_has_memos(), "本物のメモがない（仕組みだけのリポジトリ）")
class RepositoryTest(unittest.TestCase):
    """このリポジトリにコミットされている中身のテスト。"""

    def test_committed_outputs_are_up_to_date(self):
        """リポジトリにコミットされている生成物が最新であること（build --check）。"""
        with Workspace(real=True) as ws:
            p = ws.run("build", "--check", check=False)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_rebuild_from_sources_matches_repository(self):
        """自動生成ブロックと生成物をすべて消してから build すると、リポジトリと同じ中身に戻ること。"""
        with Workspace(real=True) as ws:
            strip_generated(ws)
            ws.run("build")
            self.assertEqual(diff_names(ws.snapshot(), repo_snapshot()), [])
            self.assertEqual((ws.root / ENTRY_REL).read_bytes(), (REPO / ENTRY_REL).read_bytes())

    def test_all_memos_pass_lint(self):
        with Workspace(real=True) as ws:
            p = ws.run("lint", *ws.memo_names(), check=False)
            self.assertEqual(p.returncode, 0, p.stdout)


class BuildTest(unittest.TestCase):
    def test_rebuild_from_sources_is_stable(self):
        """生成物をすべて消して build し直すと、元と同じ中身に戻ること。"""
        with Workspace() as ws:
            before = ws.snapshot()
            entry = (ws.root / ENTRY_REL).read_bytes()
            strip_generated(ws)
            ws.run("build")
            self.assertEqual(diff_names(ws.snapshot(), before), [])
            self.assertEqual((ws.root / ENTRY_REL).read_bytes(), entry)
            self.assertEqual(ws.run("build", "--check", check=False).returncode, 0)

    def test_build_is_idempotent(self):
        with Workspace() as ws:
            ws.run("build")
            before = ws.snapshot()
            p = ws.run("build")
            self.assertIn("変更なし", p.stdout)
            self.assertEqual(diff_names(before, ws.snapshot()), [])

    def test_memos_json_matches_list(self):
        with Workspace() as ws:
            memos = json.loads((ws.docs / "memos.json").read_text(encoding="utf-8"))
            quizzes = json.loads((ws.docs / "quizzes.json").read_text(encoding="utf-8"))
            listed = ws.run("list").stdout.splitlines()
            self.assertEqual(len(memos), len(listed))
            self.assertEqual(sum(m["quizzes"] for m in memos), len(quizzes))
            dates = [m["date"] for m in memos]
            self.assertEqual(dates, sorted(dates, reverse=True), "memos.json は日付の新しい順")
            files = {m["file"] for m in memos}
            self.assertTrue({q["file"] for q in quizzes} <= files)
            self.assertNotIn("index.html", files)
            self.assertNotIn("quiz.html", files)

    def test_sample_quizzes_are_collected(self):
        with Workspace() as ws:
            quizzes = json.loads((ws.docs / "quizzes.json").read_text(encoding="utf-8"))
            self.assertEqual([q["file"] for q in quizzes], ["sample.html"] * 3)
            self.assertEqual([q["answer"] for q in quizzes], [1, 0, 2])
            memos = {m["file"]: m for m in json.loads((ws.docs / "memos.json").read_text(encoding="utf-8"))}
            self.assertEqual(memos["sample.html"]["quizzes"], 3)
            self.assertEqual(memos["sample-plain.html"]["quizzes"], 0)
            self.assertIn("<!-- memo:quiz", (ws.docs / "sample.html").read_text(encoding="utf-8"))
            self.assertNotIn("<!-- memo:quiz", (ws.docs / "sample-plain.html").read_text(encoding="utf-8"))

    def test_removed_memo_disappears_from_outputs(self):
        with Workspace() as ws:
            self.assertTrue((ws.docs / "md" / "sample.md").exists())
            (ws.docs / "sample.html").unlink()
            ws.run("build")
            self.assertFalse((ws.docs / "md" / "sample.md").exists())
            memos = json.loads((ws.docs / "memos.json").read_text(encoding="utf-8"))
            self.assertNotIn("sample.html", {m["file"] for m in memos})
            self.assertNotIn("sample.html", (ws.docs / "quizzes.json").read_text(encoding="utf-8"))
            self.assertNotIn("md/sample.md", (ws.docs / "llms.txt").read_text(encoding="utf-8"))

    def test_check_reports_stale_without_writing(self):
        with Workspace() as ws:
            (ws.docs / "memos.json").write_text("[]\n", encoding="utf-8")
            before = ws.snapshot()
            p = ws.run("build", "--check", check=False)
            self.assertEqual(p.returncode, 1)
            self.assertIn("memos.json", p.stdout)
            self.assertEqual(diff_names(before, ws.snapshot()), [])


class NewAddMetaTest(unittest.TestCase):
    def test_new_copies_template_and_refuses_existing(self):
        with Workspace() as ws:
            ws.run("new", "zz-sample")
            self.assertEqual((ws.docs / "zz-sample.html").read_text(encoding="utf-8"),
                             (REPO / ".claude/skills/memo-style/template.html").read_text(encoding="utf-8"))
            self.assertNotEqual(ws.run("new", "zz-sample", check=False).returncode, 0)

    def test_invalid_and_reserved_names_are_rejected(self):
        with Workspace() as ws:
            before = ws.snapshot()
            for name in ("Bad_Name", "index", "quiz", "a--b"):
                with self.subTest(name=name):
                    p = ws.run("new", name, check=False)
                    self.assertNotEqual(p.returncode, 0)
            self.assertEqual(diff_names(before, ws.snapshot()), [])  # index.html などを上書きしていない

    def test_add_strips_code_fence_and_needs_force_to_overwrite(self):
        with Workspace() as ws:
            src = ws.root / "pasted.md"
            src.write_text("```html\n<!DOCTYPE html>\n<html><body>x</body></html>\n```\n", encoding="utf-8")
            ws.run("add", str(src), "zz-pasted")
            self.assertEqual((ws.docs / "zz-pasted.html").read_text(encoding="utf-8"),
                             "<!DOCTYPE html>\n<html><body>x</body></html>")
            self.assertNotEqual(ws.run("add", str(src), "zz-pasted", check=False).returncode, 0)
            ws.run("add", str(src), "zz-pasted", "--force")

    def test_meta_sets_fields_escapes_and_normalizes_tags(self):
        with Workspace() as ws:
            ws.run("add", str(ws.docs / "sample.html"), "zz-meta")
            out = json.loads(ws.run("meta", "zz-meta", "--title", "T <x>", "--desc", 'D "q"',
                                    "--tags", " a, b ,,", "--date", "2026-01-02").stdout)
            self.assertEqual(out, {"file": "zz-meta.html", "title": "T <x>", "desc": 'D "q"',
                                   "tags": ["a", "b"], "date": "2026-01-02"})
            text = (ws.docs / "zz-meta.html").read_text(encoding="utf-8")
            self.assertIn("<title>T &lt;x&gt;</title>", text)
            self.assertIn('<meta name="description" content="D &quot;q&quot;">', text)
            self.assertIn('<meta property="og:title" content="T &lt;x&gt;">', text)

    def test_meta_rejects_bad_date(self):
        with Workspace() as ws:
            for bad, msg in (("2026-13-40", "ありえない"), ("tomorrow", "YYYY-MM-DD"), ("2026/01/05", "YYYY-MM-DD"),
                             ("2026-1-5", "YYYY-MM-DD")):
                p = ws.run("meta", "sample", "--date", bad, check=False)
                self.assertNotEqual(p.returncode, 0, bad)
                self.assertIn(msg, p.stderr, bad)
                self.assertNotIn("Traceback", p.stderr, bad)

    def test_non_utf8_html_is_reported_by_name(self):
        with Workspace() as ws:
            src = ws.root / "sjis.html"
            src.write_bytes("<html><head><title>テスト</title></head></html>".encode("shift_jis"))
            p = ws.run("add", str(src), "sj", check=False)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("sjis.html: UTF-8 で読めません", p.stderr)
            (ws.docs / "broken.html").write_bytes(b"\xff\xfe<html>")
            p = ws.run("build", check=False)
            self.assertIn("docs/broken.html: UTF-8 で読めません", p.stderr)
            self.assertNotIn("Traceback", p.stderr)


class LintTest(unittest.TestCase):
    def test_sample_memos_pass_lint(self):
        with Workspace() as ws:
            p = ws.run("lint", *ws.memo_names(), check=False)
            self.assertEqual(p.returncode, 0, p.stdout)

    def test_fix_on_broken_draft_then_clean(self):
        with Workspace() as ws:
            draft = ws.root / "draft.html"
            draft.write_text(
                "<html><head><title>T</title>"
                '<meta name="description" content="d"><meta name="memo:tags" content="a">'
                '<meta name="memo:date" content="2026-01-01">'
                "<style>\n- { margin: 0 }\nbody { font-family: “Noto Sans JP” }\n</style></head>"
                '<body><h2 id="s">S</h2>'
                '<script type="application/json" id="memo-quiz">'
                '[{"q":"Q","choices":["a","b"],"answer":1,"ref":"#s"}]</script></body></html>',
                encoding="utf-8")
            p = ws.run("lint", str(draft), "--fix", "--backlink", check=False)
            self.assertIn("[修正]", p.stdout)
            text = draft.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("<!DOCTYPE html>"))
            self.assertIn("* { margin: 0 }", text)
            self.assertIn('"Noto Sans JP"', text)
            for needle in ('<meta charset="UTF-8">', 'name="viewport"', 'id="memo-backlink"',
                           "<!-- memo:head", "<!-- memo:quiz", "assets/memo-quiz.js"):
                self.assertIn(needle, text)
            again = ws.run("lint", str(draft), check=False)
            self.assertEqual(again.returncode, 0, again.stdout)
            self.assertIn("OK", again.stdout)

    def test_lint_reports_quiz_problems(self):
        with Workspace() as ws:
            draft = ws.root / "draft.html"
            draft.write_text(
                '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>T</title></head><body>'
                '<a href="index.html">x</a>'
                '<script type="application/json" id="memo-quiz">'
                '[{"q":"Q","choices":["a","b"],"answer":0,"ref":"#nowhere"}]</script></body></html>',
                encoding="utf-8")
            p = ws.run("lint", str(draft), check=False)
            self.assertEqual(p.returncode, 1)
            self.assertIn("#nowhere", p.stdout)
            self.assertIn("説明", p.stdout)


class PreviewTest(unittest.TestCase):
    def test_memo_preview_inlines_quiz_assets(self):
        with Workspace() as ws:
            src_before = (ws.docs / "sample.html").read_bytes()
            out = ws.root / "out" / "sample.html"
            ws.run("preview", "sample", "-o", str(out))
            text = out.read_text(encoding="utf-8")
            self.assertNotIn("assets/memo-quiz.css", text)
            self.assertNotIn("assets/memo-quiz.js", text)
            self.assertIn("#memo-quiz-ui", text)  # CSS の中身
            self.assertIn("function refLink", text)  # JS の中身
            self.assertEqual((ws.docs / "sample.html").read_bytes(), src_before)

    def test_index_and_quiz_preview_embed_data(self):
        with Workspace() as ws:
            memos = json.loads((ws.docs / "memos.json").read_text(encoding="utf-8"))
            for page in ("index", "quiz"):
                with self.subTest(page=page):
                    out = ws.root / f"{page}.html"
                    ws.run("preview", page, "-o", str(out))
                    text = out.read_text(encoding="utf-8")
                    m = re.search(r"window\.MEMO_DATA = (.*?);\n</script>", text, re.S)
                    self.assertIsNotNone(m)
                    data = json.loads(m.group(1))
                    self.assertEqual(data["memos.json"], memos)
                    self.assertLess(text.index("window.MEMO_DATA"), text.index("loadJSON"))

    def test_preview_refuses_to_overwrite_source(self):
        with Workspace() as ws:
            p = ws.run("preview", "sample", "-o", str(ws.docs / "sample.html"), check=False)
            self.assertNotEqual(p.returncode, 0)


class PathUrlTest(unittest.TestCase):
    def test_path_and_url(self):
        with Workspace() as ws:
            self.assertEqual(ws.run("path", "sample").stdout.strip(), str(ws.docs / "sample.html"))
            self.assertEqual(ws.run("path", "sample", "--md").stdout.strip(), str(ws.docs / "md" / "sample.md"))
            cname = (ws.docs / "CNAME").read_text(encoding="utf-8").strip()
            self.assertEqual(ws.run("url", "sample").stdout.strip(), f"https://{cname}/sample.html")
            self.assertEqual(ws.run("url").stdout.strip(), f"https://{cname}/")


class SiteConfigTest(unittest.TestCase):
    """memo.config.json の値がページ・llms.txt・入口スキル・コマンドに入ること。"""

    def config(self, ws: Workspace) -> dict:
        return json.loads((ws.root / "memo.config.json").read_text(encoding="utf-8"))

    def test_config_command(self):
        with Workspace() as ws:
            self.assertEqual(ws.run("config", "branch").stdout.strip(), "main")
            self.assertEqual(ws.run("config", "site_url").stdout.strip(), "https://memo.example.com/")
            shown = json.loads(ws.run("config").stdout)
            self.assertEqual(shown["repository"], "example/test-memo")
            self.assertNotEqual(ws.run("config", "nope", check=False).returncode, 0)

    def test_site_values_are_filled_into_pages(self):
        with Workspace() as ws:
            index = (ws.docs / "index.html").read_text(encoding="utf-8")
            quiz = (ws.docs / "quiz.html").read_text(encoding="utf-8")
            self.assertIn('<title data-memo-site="{site_name}">TEST MEMO</title>', index)
            self.assertIn('>テスト用のメモ置き場</p>', index)
            self.assertIn('href="https://github.com/example/test-memo"', index)
            self.assertIn('<meta property="og:site_name" content="TEST MEMO">', index)
            self.assertIn('<meta property="og:url" content="https://memo.example.com/">', index)
            self.assertIn(">TEST MEMO クイズ</title>", quiz)
            self.assertIn('content="TEST MEMO の確認クイズから', quiz)
            llms = (ws.docs / "llms.txt").read_text(encoding="utf-8")
            self.assertTrue(llms.startswith("# TEST MEMO\n\n> テスト用のメモの集まり。\n"))

    def test_changing_config_updates_everything_on_build(self):
        with Workspace() as ws:
            cfg = {**self.config(ws), "site_name": "NOTES", "repository": "alice/notes", "branch": "trunk",
                   "branding": {"accent": "#ff5500", "accent_light": "#aa3300"}}
            (ws.root / "memo.config.json").write_text(json.dumps(cfg), encoding="utf-8")
            (ws.docs / "CNAME").unlink()
            p = ws.run("build", "--check", check=False)
            self.assertEqual(p.returncode, 1)
            self.assertIn("entry-skill/SKILL.md", p.stdout)
            ws.run("build")
            index = (ws.docs / "index.html").read_text(encoding="utf-8")
            self.assertIn(">NOTES</h1>", index)
            self.assertIn('content="https://alice.github.io/notes/"', index)
            sample = (ws.docs / "sample.html").read_text(encoding="utf-8")
            self.assertIn('<meta property="og:site_name" content="NOTES">', sample)
            for page_text in (index, sample, (ws.docs / "quiz.html").read_text(encoding="utf-8")):
                self.assertIn("html:root{--accent:#aa3300}", page_text)
                self.assertIn("html:root{--accent:#ff5500}}", page_text)
            entry = (ws.root / ENTRY_REL).read_text(encoding="utf-8")
            self.assertIn("https://github.com/alice/notes.git notes", entry)
            self.assertIn("raw.githubusercontent.com/alice/notes/trunk/README.md", entry)
            self.assertEqual(ws.run("url").stdout.strip(), "https://alice.github.io/notes/")
            self.assertEqual(ws.run("build", "--check", check=False).returncode, 0)

    def test_broken_config_stops_with_message_not_traceback(self):
        with Workspace() as ws:
            (ws.root / "memo.config.json").write_text('{"utc_offset_hours": "9"}', encoding="utf-8")
            p = ws.run("build", check=False)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("utc_offset_hours は数値", p.stderr)
            self.assertNotIn("Traceback", p.stderr)

    def test_entry_skill_name_is_a_valid_skill_name(self):
        with Workspace() as ws:
            cfg = {**self.config(ws), "repository": "Alice/My.Notes"}
            (ws.root / "memo.config.json").write_text(json.dumps(cfg), encoding="utf-8")
            ws.run("build")
            entry = (ws.root / ENTRY_REL).read_text(encoding="utf-8")
            self.assertIn('name: "my-notes"', entry)
            self.assertIn("https://github.com/Alice/My.Notes.git My.Notes", entry)  # clone 先はリポジトリ名のまま

    def test_build_warns_when_repository_is_placeholder(self):
        with Workspace() as ws:
            self.assertNotIn("警告", ws.run("build").stderr)
            for repo in ("repo/sample", ""):
                cfg = {**self.config(ws), "repository": repo}
                (ws.root / "memo.config.json").write_text(json.dumps(cfg), encoding="utf-8")
                p = ws.run("build")  # 警告だけで止めない
                self.assertIn("警告", p.stderr)
                self.assertIn("repository", p.stderr)

    def test_unknown_config_key_is_an_error(self):
        with Workspace() as ws:
            cfg = {**self.config(ws), "sitename": "typo"}
            (ws.root / "memo.config.json").write_text(json.dumps(cfg), encoding="utf-8")
            p = ws.run("list", check=False)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("sitename", p.stderr)


if __name__ == "__main__":
    unittest.main()
