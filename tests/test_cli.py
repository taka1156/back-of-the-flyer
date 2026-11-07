"""memo.py をコマンドとして外から動かす結合テスト。

中身の作りを変えても（リファクタリングしても）通るように、コマンドの入出力と
生成されるファイルだけを見る。

ほとんどのテストは tests/fixtures/ のサンプルのメモで動く（本物のメモがなくても通る）。
RepositoryTest だけはこのリポジトリの本物のメモを確かめ、メモが 1 本もなければ飛ばす。
"""
from __future__ import annotations

import json
import re
import shutil
import unittest

from helpers import ENTRY_REL, REPO, Workspace, diff_names, repo_has_memos

GENERATED_BLOCKS = (r"<!-- memo:head.*?<!-- /memo:head -->\n?", r"<!-- memo:quiz.*?<!-- /memo:quiz -->\n?")
GENERATED_IN_DOCS = ("memos.json", "quizzes.json", "llms.txt", "md")


def remove_dist(ws: Workspace) -> None:
    shutil.rmtree(ws.dist, ignore_errors=True)


@unittest.skipUnless(repo_has_memos(), "本物のメモがない（仕組みだけのリポジトリ）")
class RepositoryTest(unittest.TestCase):
    """このリポジトリにコミットされている中身のテスト。"""

    def test_sources_have_no_generated_outputs(self):
        """src/ は原本だけ: 自動生成ブロックも生成物も入っていないこと。"""
        with Workspace(real=True) as ws:
            for page in sorted(ws.src.glob("*.html")):
                text = page.read_text(encoding="utf-8")
                for pat in GENERATED_BLOCKS:
                    self.assertIsNone(re.search(pat, text, re.S), f"{page.name} に自動生成ブロックがある")
            for name in GENERATED_IN_DOCS:
                self.assertFalse((ws.src / name).exists(), f"src/{name} は build が dist/ に作る")

    def test_build_writes_only_dist(self):
        """本物のメモで build しても src/ は 1 バイトも変わらず、dist/ に全ページができること。"""
        with Workspace(real=True) as ws:
            before = ws.snapshot()
            ws.run("build")
            self.assertEqual(diff_names(before, ws.snapshot()), [])
            for name in ws.memo_names():
                self.assertIn("<!-- memo:head", ws.read(f"{name}.html"), name)
                self.assertTrue((ws.dist / "md" / f"{name}.md").is_file(), name)
            self.assertEqual(ws.run("build", "--check", check=False).returncode, 0)

    def test_all_memos_pass_lint(self):
        with Workspace(real=True) as ws:
            p = ws.run("lint", *ws.memo_names(), check=False)
            self.assertEqual(p.returncode, 0, p.stdout)


class BuildTest(unittest.TestCase):
    def test_build_does_not_touch_sources(self):
        with Workspace() as ws:
            before = ws.snapshot()
            remove_dist(ws)
            ws.run("build")
            self.assertEqual(diff_names(before, ws.snapshot()), [])

    def test_rebuild_from_scratch_is_stable(self):
        """dist/ を消して build し直すと、元と同じ中身に戻ること。"""
        with Workspace() as ws:
            before = ws.snapshot("dist")
            remove_dist(ws)
            ws.run("build")
            self.assertEqual(diff_names(ws.snapshot("dist"), before), [])
            self.assertEqual(ws.run("build", "--check", check=False).returncode, 0)

    def test_dist_is_a_complete_site(self):
        """dist/ だけで公開できること: 原本の共通ファイルのコピーと、生成物がそろっている。"""
        with Workspace() as ws:
            for rel in ("index.html", "quiz.html", "settings.html", "sample.html", "sample-plain.html",
                        "CNAME", "assets/memo-quiz.css", "assets/memo-quiz.js", "memos.json", "quizzes.json",
                        "llms.txt", "md/sample.md", str(ENTRY_REL)):
                self.assertTrue((ws.dist / rel).is_file(), rel)
            self.assertEqual((ws.dist / "assets" / "memo-quiz.js").read_bytes(),
                             (ws.src / "assets" / "memo-quiz.js").read_bytes())
            self.assertIn("<!-- memo:head", ws.read("sample.html"))
            self.assertNotIn("<!-- memo:head", (ws.src / "sample.html").read_text(encoding="utf-8"))

    def test_build_is_idempotent(self):
        with Workspace() as ws:
            ws.run("build")
            before = ws.snapshot("dist")
            p = ws.run("build")
            self.assertIn("変更なし", p.stdout)
            self.assertEqual(diff_names(before, ws.snapshot("dist")), [])

    def test_memos_json_matches_list(self):
        with Workspace() as ws:
            memos = json.loads(ws.read("memos.json"))
            quizzes = json.loads(ws.read("quizzes.json"))
            listed = ws.run("list").stdout.splitlines()
            self.assertEqual(len(memos), len(listed))
            self.assertEqual(sum(m["quizzes"] for m in memos), len(quizzes))
            dates = [m["date"] for m in memos]
            self.assertEqual(dates, sorted(dates, reverse=True), "memos.json は日付の新しい順")
            files = {m["file"] for m in memos}
            self.assertTrue({q["file"] for q in quizzes} <= files)
            self.assertNotIn("index.html", files)
            self.assertNotIn("quiz.html", files)
            self.assertNotIn("settings.html", files)
            self.assertNotIn("roadmap.html", files)
            self.assertFalse((ws.dist / "md" / "settings.md").exists())
            self.assertFalse((ws.dist / "md" / "roadmap.md").exists())
            self.assertNotIn("settings", ws.read("llms.txt"))
            self.assertNotIn("roadmap", ws.read("llms.txt"))

    def test_sample_quizzes_are_collected(self):
        with Workspace() as ws:
            quizzes = json.loads(ws.read("quizzes.json"))
            self.assertEqual([q["file"] for q in quizzes], ["sample.html"] * 3)
            self.assertEqual([q["answer"] for q in quizzes], [1, 0, 2])
            memos = {m["file"]: m for m in json.loads(ws.read("memos.json"))}
            self.assertEqual(memos["sample.html"]["quizzes"], 3)
            self.assertEqual(memos["sample-plain.html"]["quizzes"], 0)
            self.assertIn("<!-- memo:quiz", ws.read("sample.html"))
            self.assertNotIn("<!-- memo:quiz", ws.read("sample-plain.html"))

    def test_removed_memo_disappears_from_outputs(self):
        with Workspace() as ws:
            self.assertTrue((ws.dist / "md" / "sample.md").exists())
            (ws.src / "sample.html").unlink()
            p = ws.run("build")
            self.assertIn("削除", p.stdout)
            self.assertFalse((ws.dist / "sample.html").exists())
            self.assertFalse((ws.dist / "md" / "sample.md").exists())
            memos = json.loads(ws.read("memos.json"))
            self.assertNotIn("sample.html", {m["file"] for m in memos})
            self.assertNotIn("sample.html", ws.read("quizzes.json"))
            self.assertNotIn("md/sample.md", ws.read("llms.txt"))

    def test_removed_asset_disappears_from_dist(self):
        with Workspace() as ws:
            (ws.src / "assets" / "zz.txt").write_text("x", encoding="utf-8")
            ws.run("build")
            self.assertTrue((ws.dist / "assets" / "zz.txt").is_file())
            (ws.src / "assets" / "zz.txt").unlink()
            ws.run("build")
            self.assertFalse((ws.dist / "assets" / "zz.txt").exists())

    def test_check_reports_stale_without_writing(self):
        with Workspace() as ws:
            (ws.dist / "memos.json").write_text("[]\n", encoding="utf-8")
            before = ws.snapshot("dist")
            p = ws.run("build", "--check", check=False)
            self.assertEqual(p.returncode, 1)
            self.assertIn("memos.json", p.stdout)
            self.assertEqual(diff_names(before, ws.snapshot("dist")), [])


class NewAddMetaTest(unittest.TestCase):
    def test_new_copies_template_and_refuses_existing(self):
        with Workspace() as ws:
            ws.run("new", "zz-sample")
            self.assertEqual((ws.src / "zz-sample.html").read_text(encoding="utf-8"),
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
            self.assertEqual((ws.src / "zz-pasted.html").read_text(encoding="utf-8"),
                             "<!DOCTYPE html>\n<html><body>x</body></html>")
            self.assertNotEqual(ws.run("add", str(src), "zz-pasted", check=False).returncode, 0)
            ws.run("add", str(src), "zz-pasted", "--force")

    def test_meta_sets_fields_escapes_and_normalizes_tags(self):
        with Workspace() as ws:
            ws.run("add", str(ws.src / "sample.html"), "zz-meta")
            out = json.loads(ws.run("meta", "zz-meta", "--title", "T <x>", "--desc", 'D "q"',
                                    "--tags", " a, b ,,", "--date", "2026-01-02").stdout)
            self.assertEqual(out, {"file": "zz-meta.html", "title": "T <x>", "desc": 'D "q"',
                                   "tags": ["a", "b"], "date": "2026-01-02"})
            text = (ws.src / "zz-meta.html").read_text(encoding="utf-8")
            self.assertIn("<title>T &lt;x&gt;</title>", text)
            self.assertIn('<meta name="description" content="D &quot;q&quot;">', text)
            self.assertNotIn("<!-- memo:head", text)  # 原本には自動生成ブロックを入れない
            ws.run("build")
            self.assertIn('<meta property="og:title" content="T &lt;x&gt;">', ws.read("zz-meta.html"))

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
            (ws.src / "broken.html").write_bytes(b"\xff\xfe<html>")
            p = ws.run("build", check=False)
            self.assertIn("src/broken.html: UTF-8 で読めません", p.stderr)
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
            for needle in ('<meta charset="UTF-8">', 'name="viewport"', 'id="memo-backlink"'):
                self.assertIn(needle, text)
            for needle in ("<!-- memo:head", "<!-- memo:quiz"):  # 自動生成ブロックは build が dist/ にだけ入れる
                self.assertNotIn(needle, text)
            again = ws.run("lint", str(draft), check=False)
            self.assertEqual(again.returncode, 0, again.stdout)
            self.assertIn("OK", again.stdout)

    def test_fix_strips_generated_blocks_from_source(self):
        """公開ページ（dist/）からコピーした HTML を取り込んでも、lint --fix で原本の形に戻ること。"""
        with Workspace() as ws:
            ws.run("add", str(ws.dist / "sample.html"), "zz-copied")
            p = ws.run("lint", "zz-copied", check=False)
            self.assertEqual(p.returncode, 1)
            self.assertIn("自動生成ブロック", p.stdout)
            ws.run("lint", "zz-copied", "--fix")
            self.assertEqual((ws.src / "zz-copied.html").read_text(encoding="utf-8"),
                             (ws.src / "sample.html").read_text(encoding="utf-8"))

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
            src_before = (ws.src / "sample.html").read_bytes()
            out = ws.root / "out" / "sample.html"
            ws.run("preview", "sample", "-o", str(out))
            text = out.read_text(encoding="utf-8")
            self.assertNotIn("assets/memo-quiz.css", text)
            self.assertNotIn("assets/memo-quiz.js", text)
            self.assertIn("#memo-quiz-ui", text)  # CSS の中身
            self.assertIn("function refLink", text)  # JS の中身
            self.assertEqual((ws.src / "sample.html").read_bytes(), src_before)

    def test_index_and_quiz_preview_embed_data(self):
        with Workspace() as ws:
            memos = json.loads(ws.read("memos.json"))
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
            p = ws.run("preview", "sample", "-o", str(ws.src / "sample.html"), check=False)
            self.assertNotEqual(p.returncode, 0)


class PathUrlTest(unittest.TestCase):
    def test_path_and_url(self):
        with Workspace() as ws:
            self.assertEqual(ws.run("path", "sample").stdout.strip(), str(ws.src / "sample.html"))
            self.assertEqual(ws.run("path", "sample", "--md").stdout.strip(), str(ws.dist / "md" / "sample.md"))
            cname = (ws.src / "CNAME").read_text(encoding="utf-8").strip()
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
            index = ws.read("index.html")
            quiz = ws.read("quiz.html")
            self.assertIn('<title data-memo-site="{site_name}">TEST MEMO</title>', index)
            self.assertIn('>テスト用のメモ置き場</p>', index)
            self.assertIn('href="https://github.com/example/test-memo"', index)
            self.assertIn('<meta property="og:site_name" content="TEST MEMO">', index)
            self.assertIn('<meta property="og:url" content="https://memo.example.com/">', index)
            self.assertIn(">TEST MEMO クイズ</title>", quiz)
            self.assertIn('content="TEST MEMO の確認クイズから', quiz)
            llms = ws.read("llms.txt")
            self.assertTrue(llms.startswith("# TEST MEMO\n\n> テスト用のメモの集まり。\n"))

    def test_changing_config_updates_everything_on_build(self):
        with Workspace() as ws:
            cfg = {**self.config(ws), "site_name": "NOTES", "repository": "alice/notes", "branch": "trunk",
                   "branding": {"accent": "#ff5500", "accent_light": "#aa3300"}}
            (ws.root / "memo.config.json").write_text(json.dumps(cfg), encoding="utf-8")
            (ws.src / "CNAME").unlink()
            p = ws.run("build", "--check", check=False)
            self.assertEqual(p.returncode, 1)
            self.assertIn("entry-skill/SKILL.md", p.stdout)
            ws.run("build")
            index = ws.read("index.html")
            self.assertIn(">NOTES</h1>", index)
            self.assertIn('content="https://alice.github.io/notes/"', index)
            sample = ws.read("sample.html")
            self.assertIn('<meta property="og:site_name" content="NOTES">', sample)
            for page_text in (index, sample, ws.read("quiz.html")):
                self.assertIn("html:root{--accent:#aa3300}", page_text)
                self.assertIn("html:root{--accent:#ff5500}}", page_text)
            entry = ws.read(str(ENTRY_REL))
            self.assertIn("https://github.com/alice/notes.git notes", entry)
            self.assertIn("raw.githubusercontent.com/alice/notes/trunk/README.md", entry)
            self.assertEqual(ws.run("url").stdout.strip(), "https://alice.github.io/notes/")
            self.assertEqual(ws.run("build", "--check", check=False).returncode, 0)

    def test_settings_page_shows_current_accent_and_workflow_link(self):
        with Workspace() as ws:
            settings = ws.read("settings.html")
            self.assertIn('id="cur-dark" data-memo-site="{accent}">#00d4ff</code>', settings)
            self.assertIn('id="cur-light" data-memo-site="{accent_light}">#007f99</code>', settings)  # ライト用は自動
            self.assertIn('href="https://github.com/example/test-memo/actions/workflows/set-accent.yml"', settings)
            self.assertIn(">TEST MEMO 設定</title>", settings)
            self.assertIn('<meta name="robots" content="noindex">', settings)
            index = ws.read("index.html")
            self.assertIn('<a href="settings.html">設定</a>', index)  # トップのフッターから開ける

    def test_roadmap_page_is_off_by_default(self):
        """ロードマップはオプション: memo.config.json に roadmap がなければ公開せず、トップにもリンクを出さない。"""
        with Workspace() as ws:
            self.assertFalse((ws.dist / "roadmap.html").exists())
            index = ws.read("index.html")
            self.assertNotIn("roadmap.html", index)
            self.assertNotIn('data-memo-if="roadmap"', index)
            self.assertIn('<a href="settings.html">設定</a>', index)  # ほかのリンクは残る
            self.assertEqual(ws.run("build", "--check", check=False).returncode, 0)

    def test_roadmap_page_is_special_and_linked_from_top_when_on(self):
        """オンにすると、設定と同じ特別なページとして公開される: 一覧に載らず、クイズも付かず、トップのフッターから開ける。"""
        with Workspace() as ws:
            cfg = self.config(ws)
            (ws.root / "memo.config.json").write_text(json.dumps({**cfg, "roadmap": True}, ensure_ascii=False),
                                                      encoding="utf-8")
            ws.run("build")
            roadmap = ws.read("roadmap.html")
            self.assertIn(">TEST MEMO ロードマップ</title>", roadmap)
            self.assertIn('<meta name="robots" content="noindex">', roadmap)
            self.assertIn("<!-- memo:head", roadmap)
            self.assertNotIn("memo-quiz.js", roadmap)
            self.assertIn("fetch('memos.json'", roadmap)  # チェックは一覧データから付ける
            self.assertIn('<a href="roadmap.html">ロードマップ</a>', ws.read("index.html"))
            self.assertNotIn("roadmap.html", {m["file"] for m in json.loads(ws.read("memos.json"))})
            self.assertFalse((ws.dist / "md" / "roadmap.md").exists())
            out = ws.root / "pv.html"
            ws.run("preview", "roadmap", "-o", str(out))
            self.assertIn("window.MEMO_DATA", out.read_text(encoding="utf-8"))  # プレビューでも一覧データが入る
            # オフに戻すと dist/ からも消える
            (ws.root / "memo.config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
            ws.run("build")
            self.assertFalse((ws.dist / "roadmap.html").exists())
            self.assertNotIn("roadmap.html", ws.read("index.html"))

    def test_quiz_is_on_by_default(self):
        """クイズは既定でオン: quiz.html・quizzes.json・各メモのクイズ表示・トップのランダムクイズを出す。"""
        with Workspace() as ws:
            self.assertTrue((ws.dist / "quiz.html").exists())
            self.assertTrue((ws.dist / "quizzes.json").exists())
            self.assertIn("<!-- memo:quiz", ws.read("sample.html"))
            self.assertIn('id="rq"', ws.read("index.html"))
            self.assertGreater(sum(m["quizzes"] for m in json.loads(ws.read("memos.json"))), 0)

    def test_quiz_off_generates_nothing_for_quizzes(self):
        """quiz を false にすると、クイズに関わるものを何も生成しない（オンに戻せば元どおり）。"""
        with Workspace() as ws:
            cfg = self.config(ws)
            (ws.root / "memo.config.json").write_text(json.dumps({**cfg, "quiz": False}, ensure_ascii=False),
                                                      encoding="utf-8")
            p = ws.run("build")
            self.assertIn("クイズはオフ", p.stdout)
            self.assertFalse((ws.dist / "quiz.html").exists())
            self.assertFalse((ws.dist / "quizzes.json").exists())
            self.assertFalse((ws.dist / "assets" / "memo-quiz.js").exists())
            self.assertFalse((ws.dist / "assets" / "memo-quiz.css").exists())
            sample = ws.read("sample.html")
            self.assertNotIn("<!-- memo:quiz", sample)
            self.assertNotIn("memo-quiz.js", sample)
            index = ws.read("index.html")
            self.assertNotIn('id="rq"', index)
            self.assertNotIn("quiz.html", index)
            self.assertNotIn('data-memo-if="quiz"', index)
            self.assertEqual({m["quizzes"] for m in json.loads(ws.read("memos.json"))}, {0})
            self.assertEqual(ws.run("build", "--check", check=False).returncode, 0)
            out = ws.root / "pv.html"
            ws.run("preview", "sample", "-o", str(out))
            self.assertNotIn("memo-quiz-ui", out.read_text(encoding="utf-8"))
            # 原本の問題データは残っているので、オンに戻せば元どおり出る
            (ws.root / "memo.config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
            ws.run("build")
            self.assertTrue((ws.dist / "quiz.html").exists())
            self.assertTrue((ws.dist / "quizzes.json").exists())
            self.assertTrue((ws.dist / "assets" / "memo-quiz.js").exists())
            self.assertIn("<!-- memo:quiz", ws.read("sample.html"))

    def test_accent_command_then_build_changes_every_page(self):
        with Workspace() as ws:
            p = ws.run("accent", "#3ddc97", "#0f7a50")
            self.assertIn("accent=#3ddc97 accent_light=#0f7a50", p.stdout)
            cfg = self.config(ws)
            self.assertEqual(cfg["branding"], {"accent": "#3ddc97", "accent_light": "#0f7a50"})
            self.assertEqual(cfg["site_name"], "TEST MEMO")  # ほかの項目は残る
            self.assertEqual(ws.run("build", "--check", check=False).returncode, 1)
            ws.run("build")
            for name in ("index.html", "quiz.html", "settings.html", "sample.html", "sample-plain.html"):
                text = ws.read(name)
                self.assertIn("html:root{--accent:#0f7a50}", text, name)
                self.assertIn("html:root{--accent:#3ddc97}}", text, name)
            settings = ws.read("settings.html")
            self.assertIn('data-memo-site="{accent}">#3ddc97</code>', settings)
            # 同じ色をもう一度入れても何も変わらない
            before = ws.snapshot("dist")
            ws.run("accent", "#3ddc97", "#0f7a50")
            ws.run("build")
            self.assertEqual(diff_names(before, ws.snapshot("dist")), [])
            # ライト用を省くと自動で決まる
            p = ws.run("accent", "#3ddc97")
            self.assertIn("（accent から自動）", p.stdout)
            self.assertNotIn("accent_light", self.config(ws)["branding"])

    def test_accent_command_rejects_bad_color_without_changing_config(self):
        with Workspace() as ws:
            before = (ws.root / "memo.config.json").read_text(encoding="utf-8")
            p = ws.run("accent", "green", check=False)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("branding.accent は #rgb か #rrggbb", p.stderr)
            self.assertNotIn("Traceback", p.stderr)
            self.assertEqual((ws.root / "memo.config.json").read_text(encoding="utf-8"), before)

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
            entry = ws.read(str(ENTRY_REL))
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

    def test_deploy_branch_setting(self):
        with Workspace() as ws:
            self.assertEqual(ws.run("config", "deploy_branch").stdout.strip(), "dist")
            for value, msg in (("main", "別のブランチ"), ("a b", "空白")):
                cfg = {**self.config(ws), "deploy_branch": value}
                (ws.root / "memo.config.json").write_text(json.dumps(cfg), encoding="utf-8")
                p = ws.run("config", check=False)
                self.assertNotEqual(p.returncode, 0, value)
                self.assertIn(msg, p.stderr, value)

    def test_unknown_config_key_is_an_error(self):
        with Workspace() as ws:
            cfg = {**self.config(ws), "sitename": "typo"}
            (ws.root / "memo.config.json").write_text(json.dumps(cfg), encoding="utf-8")
            p = ws.run("list", check=False)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("sitename", p.stderr)


if __name__ == "__main__":
    unittest.main()
