"""テスト用の共通処理（標準ライブラリのみ）。

テストは本物のリポジトリを書き換えないよう、一時フォルダに作った「作業用リポジトリ」で memo.py を動かす。
memo.py は自分の置き場所からリポジトリの場所を決めるので、コピーした scripts/memo.py はコピー先の
docs/ と memo.config.json を対象にする。

作業用リポジトリは 2 種類:

- Workspace()          仕組みのテスト用。仕組みのファイル（scripts/、テンプレート、docs/ の index.html・
                       assets/）に、tests/fixtures/ のサンプルのメモと設定を組み合わせて build したもの。
                       本物のメモが 1 本もなくても（仕組みだけを取り出したリポジトリでも）動く。
- Workspace(real=True) このリポジトリの docs/ と設定をそのままコピーしたもの。コミットされている生成物が
                       最新かどうかなど、本物の中身を確かめるテストと tests/snapshot.py が使う。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
FIXTURES = REPO / "tests" / "fixtures"
TEMPLATE_REL = Path(".claude/skills/memo-style/template.html")
CONFIG_NAME = "memo.config.json"
ENTRY_REL = Path("entry-skill/SKILL.md")
# docs/ のうち、メモではなく仕組みの一部として持っていくもの
MECHANISM_DOCS = ("index.html", "assets")
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def repo_has_memos() -> bool:
    """このリポジトリに本物のメモがあるか（仕組みだけのリポジトリなら False）。"""
    return any(p.name not in MECHANISM_DOCS for p in (REPO / "docs").glob("*.html"))


class Workspace:
    """一時フォルダに作ったリポジトリのコピー。with 文で使う。"""

    def __init__(self, real: bool = False) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="memo-test-")
        self.root = Path(self._tmp.name)
        shutil.copytree(SCRIPTS, self.root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / TEMPLATE_REL).parent.mkdir(parents=True)
        shutil.copy(REPO / TEMPLATE_REL, self.root / TEMPLATE_REL)
        if real:
            shutil.copytree(REPO / "docs", self.docs)
            for rel in (Path(CONFIG_NAME), ENTRY_REL):
                if (REPO / rel).is_file():
                    (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(REPO / rel, self.root / rel)
        else:
            self.docs.mkdir()
            for name in MECHANISM_DOCS:
                src = REPO / "docs" / name
                if src.is_dir():
                    shutil.copytree(src, self.docs / name)
                elif src.is_file():
                    shutil.copy(src, self.docs / name)
            shutil.copytree(FIXTURES / "docs", self.docs, dirs_exist_ok=True)
            shutil.copy(FIXTURES / CONFIG_NAME, self.root / CONFIG_NAME)
            self.run("build")  # サンプルのメモから生成物を作り、「コミット済みの状態」にする
        # memo:date が無いメモは git の履歴から日付を取るので、git リポジトリにしておく
        env = {**os.environ, **GIT_ENV}
        for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "base"]):
            subprocess.run(cmd, cwd=self.root, check=True, env=env)

    def __enter__(self) -> "Workspace":
        return self

    def __exit__(self, *exc) -> None:
        self._tmp.cleanup()

    @property
    def docs(self) -> Path:
        return self.root / "docs"

    def memo_names(self) -> list[str]:
        return sorted(p.stem for p in self.docs.glob("*.html") if p.name not in MECHANISM_DOCS)

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """コピー先の memo.py を実行する。"""
        p = subprocess.run(
            [sys.executable, "-B", str(self.root / "scripts" / "memo.py"), *args],
            cwd=self.root, capture_output=True, text=True,
        )
        if check and p.returncode != 0:
            raise AssertionError(f"memo.py {' '.join(args)} が失敗 ({p.returncode}):\n{p.stdout}\n{p.stderr}")
        return p

    def snapshot(self) -> dict[str, bytes]:
        """docs/ 以下の全ファイルの中身（比較用）。"""
        return {str(p.relative_to(self.docs)): p.read_bytes()
                for p in sorted(self.docs.rglob("*")) if p.is_file()}


def repo_snapshot() -> dict[str, bytes]:
    docs = REPO / "docs"
    return {str(p.relative_to(docs)): p.read_bytes()
            for p in sorted(docs.rglob("*")) if p.is_file()}


def diff_names(a: dict[str, bytes], b: dict[str, bytes]) -> list[str]:
    return sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))
