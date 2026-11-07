#!/usr/bin/env python3
"""memo.py の全コマンドの出力をフォルダに保存する（リファクタリングの前後比較用）。

    python3 tests/snapshot.py OUTDIR [--fixtures]

リポジトリを一時フォルダにコピーし、そのコピーの上で次を実行して結果を OUTDIR に保存する。
リポジトリ自体は書き換えない。本物のメモがないとき（仕組みだけのリポジトリ）や --fixtures を
付けたときは、tests/fixtures/ のサンプルのメモで実行する。

- 自動生成ブロックと生成物をすべて消してから build（docs/ 全体を build/ に保存）
- 全メモの lint と preview、index の preview
- 壊れた下書きの lint --fix と preview、new / add / meta / path / url / list

変更の前と後で 1 回ずつ実行し、`diff -r 前 後` で何も出なければ出力は変わっていない。
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from helpers import ENTRY_REL, Workspace, repo_has_memos

BROKEN_DRAFT = (
    "<html><head><title>T</title>"
    '<meta name="description" content="d"><meta name="memo:tags" content="a">'
    '<meta name="memo:date" content="2026-01-01">'
    "<style>\n- { margin: 0 }\nbody { font-family: “Noto Sans JP” }\n</style></head>"
    '<body><h2 id="s">S</h2><svg><text>図</text></svg>'
    '<script type="application/json" id="memo-quiz">'
    '[{"q":"Q","choices":["a","b"],"answer":1,"ref":"#s"}]</script></body></html>'
)


def main(out: Path, fixtures: bool) -> None:
    if out.exists():
        sys.exit(f"{out} はすでにあります（空のフォルダ名を指定）")
    with Workspace(real=not fixtures) as ws:
        log: list[str] = []

        def run(*args: str) -> str:
            p = ws.run(*args, check=False)
            def norm(t: str) -> str:  # 実行ごとに変わるパスを置き換えて、前後で比べられるようにする
                return t.replace(str(out), "OUT").replace(str(ws.root), "ROOT")
            log.append(f"$ memo.py {norm(' '.join(args))}  [exit {p.returncode}]\n{norm(p.stdout + p.stderr)}")
            return p.stdout

        for page in ws.docs.glob("*.html"):
            text = page.read_text(encoding="utf-8")
            text = re.sub(r"<!-- memo:head.*?<!-- /memo:head -->\n?", "", text, flags=re.S)
            page.write_text(text, encoding="utf-8")
        for name in ("memos.json", "llms.txt"):
            (ws.docs / name).unlink()
        for md in (ws.docs / "md").glob("*.md"):
            md.unlink()
        (ws.root / ENTRY_REL).unlink(missing_ok=True)
        run("build")
        run("build", "--check")
        run("list")
        shutil.copytree(ws.docs, out / "build")
        shutil.copy(ws.root / ENTRY_REL, out / "entry-skill.md")

        names = ws.memo_names()
        first = names[0]  # add / path / url を試すメモ
        for n in names:
            run("lint", n)
            run("preview", n, "-o", str(out / "preview" / f"{n}.html"))
        run("preview", "index", "-o", str(out / "preview" / "index.html"))

        draft = ws.root / "draft.html"
        draft.write_text(BROKEN_DRAFT, encoding="utf-8")
        run("lint", str(draft))
        run("lint", str(draft), "--fix", "--backlink")
        shutil.copy(draft, out / "draft-fixed.html")
        run("preview", str(draft), "-o", str(out / "draft-preview.html"))

        run("new", "zz-new")
        run("add", str(ws.docs / f"{first}.html"), "zz-add")
        run("meta", "zz-add", "--title", "T <x>", "--desc", 'D "q"', "--tags", " a, b ,,", "--date", "2026-01-02")
        shutil.copy(ws.docs / "zz-add.html", out / "meta.html")
        run("lint", "zz-new")
        for args in (("path", first), ("path", first, "--md"), ("url", first), ("url",),
                     ("new", "index"), ("new", "Bad_Name"), ("config",)):
            run(*args)
        (out / "log.txt").write_text("\n".join(log), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if a != "--fixtures"]
    if len(argv) != 1:
        sys.exit(__doc__)
    main(Path(argv[0]).resolve(), fixtures="--fixtures" in sys.argv or not repo_has_memos())
