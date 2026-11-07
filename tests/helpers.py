"""テスト用の共通処理（標準ライブラリのみ）。

テストは本物のリポジトリを書き換えないよう、一時フォルダに作った「作業用リポジトリ」で memo.py を動かす。
memo.py は自分の置き場所からリポジトリの場所を決めるので、コピーした scripts/memo.py はコピー先の
src/ と memo.config.json を対象にする。

作業用リポジトリは 2 種類:

- Workspace()          仕組みのテスト用。仕組みのファイル（scripts/、テンプレート、src/ の index.html・
                       settings.html・roadmap.html・assets/）に、tests/fixtures/ のサンプルのメモと設定を組み合わせて build したもの。
                       本物のメモが 1 本もなくても（仕組みだけを取り出したリポジトリでも）動く。
- Workspace(real=True) このリポジトリの src/ と設定をそのままコピーしたもの。原本がきれいか（自動生成ブロックが
                       混ざっていないか）など、本物の中身を確かめるテストと tests/snapshot.py が使う。

どちらも build の出力は作業用リポジトリの dist/ にできる（src/ は原本のまま）。
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
ENTRY_REL = Path("entry-skill/SKILL.md")  # dist/ からの相対パス
# src/ のうち、メモではなく仕組みの一部として持っていくもの
MECHANISM_DOCS = ("index.html", "settings.html", "roadmap.html", ".nojekyll", "assets")
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def repo_has_memos() -> bool:
    """このリポジトリに本物のメモがあるか（仕組みだけのリポジトリなら False）。"""
    return any(p.name not in MECHANISM_DOCS for p in (REPO / "src").glob("*.html"))


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
            shutil.copytree(REPO / "src", self.src)
            if (REPO / CONFIG_NAME).is_file():
                shutil.copy(REPO / CONFIG_NAME, self.root / CONFIG_NAME)
        else:
            self.src.mkdir()
            for name in MECHANISM_DOCS:
                src = REPO / "src" / name
                if src.is_dir():
                    shutil.copytree(src, self.src / name)
                elif src.is_file():
                    shutil.copy(src, self.src / name)
            shutil.copytree(FIXTURES / "src", self.src, dirs_exist_ok=True)
            shutil.copy(FIXTURES / CONFIG_NAME, self.root / CONFIG_NAME)
            self.run("build")  # サンプルのメモから dist/ を作っておく
        # memo:date が無いメモは git の履歴から日付を取るので、git リポジトリにしておく
        env = {**os.environ, **GIT_ENV}
        (self.root / ".gitignore").write_text("/dist/\n", encoding="utf-8")
        for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "base"]):
            subprocess.run(cmd, cwd=self.root, check=True, env=env)

    def __enter__(self) -> "Workspace":
        return self

    def __exit__(self, *exc) -> None:
        self._tmp.cleanup()

    @property
    def src(self) -> Path:
        return self.root / "src"

    @property
    def dist(self) -> Path:
        return self.root / "dist"

    def memo_names(self) -> list[str]:
        return sorted(p.stem for p in self.src.glob("*.html") if p.name not in MECHANISM_DOCS)

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """コピー先の memo.py を実行する。"""
        p = subprocess.run(
            [sys.executable, "-B", str(self.root / "scripts" / "memo.py"), *args],
            cwd=self.root, capture_output=True, text=True,
        )
        if check and p.returncode != 0:
            raise AssertionError(f"memo.py {' '.join(args)} が失敗 ({p.returncode}):\n{p.stdout}\n{p.stderr}")
        return p

    def snapshot(self, folder: str = "src") -> dict[str, bytes]:
        """src/（または dist/）以下の全ファイルの中身（比較用）。"""
        base = self.root / folder
        return {str(p.relative_to(base)): p.read_bytes()
                for p in sorted(base.rglob("*")) if p.is_file()}

    def read(self, rel: str) -> str:
        """dist/ のファイルを読む（build の出力の確認用）。"""
        return (self.dist / rel).read_text(encoding="utf-8")


def diff_names(a: dict[str, bytes], b: dict[str, bytes]) -> list[str]:
    return sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))
