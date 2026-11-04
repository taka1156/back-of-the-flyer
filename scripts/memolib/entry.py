"""claude.ai のアプリ側に置く入口スキル（entry-skill/SKILL.md）の中身。

入口スキルは「このリポジトリを取ってきて、ここのスキルに従う」だけのもので、手順は書かない。
リポジトリ名とブランチだけはアプリ側で知っている必要があるので、memo.config.json から作る。
build が生成するので手で編集しない（変えたいときはここを直す）。
"""
from __future__ import annotations

import re

from .config import BRANCH, REPOSITORY, SITE_NAME

SKILL_NAME_MAX = 64  # スキル名の長さの上限

ENTRY_NOTE = "<!-- scripts/memo.py build が memo.config.json から自動生成。手で編集しない -->"


def skill_name(repository: str) -> str:
    """リポジトリ名からスキル名を作る。スキル名に使えるのは小文字・数字・ハイフンだけなので、
    大文字は小文字にし、それ以外の文字（. _ など）はハイフンにまとめる（例: Alice/My.Notes → my-notes）。"""
    name = re.sub(r"[^a-z0-9]+", "-", repository.split("/")[-1].lower()).strip("-")
    return name[:SKILL_NAME_MAX].rstrip("-") or "memo"


def entry_skill() -> str:
    repo = REPOSITORY or "OWNER/REPO"
    folder = repo.split("/")[-1]  # clone 先のフォルダ名（git clone の既定と同じ）
    name = skill_name(repo)
    raw = f"https://raw.githubusercontent.com/{repo}/{BRANCH}"
    return f"""---
name: "{name}"
description: "{repo}（{SITE_NAME}）に関する依頼の入口。HTMLで図解してまとめる、{SITE_NAME}に保存、ファクトチェックなど。手順はGitHubのリポジトリから取得して従う。"
---
{ENTRY_NOTE}

# {name}（入口スキル）

このスキルには手順もデザイン規約も書かない。**信頼できる唯一の情報源は GitHub の `{repo}` リポジトリ**。毎回そこから最新版を取得し、そこに書かれたスキルに従う。

## 使う場面

次のような依頼（言い回しは毎回違う）:

- 「〇〇を HTML で（図とともに）まとめて」「〇〇の図解ページにして」「〇〇のメモを作って」
- 「保存して」「{SITE_NAME} に入れて」「メモに追加」
- 「さっきの説明を {SITE_NAME} にして」
- 「〇〇をファクトチェックして」「最近のメモを事実確認して」
- そのほか {SITE_NAME} リポジトリのページや一覧に関する作業

## 手順

### 1. リポジトリを取得する

作業用ディレクトリに浅くクローンする（すでにあれば更新）。

```bash
git clone --depth 1 https://github.com/{repo}.git {folder} 2>/dev/null || git -C {folder} pull -q
```

クローンできない環境では、raw URL を WebFetch で読む（README → 必要なスキルの順）。

- {raw}/README.md
- {raw}/.claude/skills/<スキル名>/SKILL.md

どちらも取得できなかったら、作り始める前にその旨を伝えて止まる。**記憶で手順や規約を再現しない。**

### 2. どのスキルを使うか決める

リポジトリの `README.md` を読み、「Claude に頼むとき」と「アプリ（claude.ai）から使うとき」の表で依頼に合うスキルを選ぶ。表に無い依頼なら `.claude/skills/` の各 SKILL.md の description を見て選ぶ。それでも合うものが無ければ、その旨を伝えて普通に対応する。

### 3. スキルに従う

選んだスキルの `SKILL.md` を最後まで読み、その手順どおりに進める。保存するかどうか・いつ保存するかも README とスキルの記述に従う（このスキル側では決めない）。

リポジトリに書き込む手順（登録・修正・push）に進むときは、`{repo}` を push 権限付きでセッションに追加してから行う。
"""
