---
name: "cheatsheet"
description: "taka1156/cheatsheet（CheatSheet）に関する依頼の入口。HTMLで図解してまとめる、CheatSheetに保存、ファクトチェックなど。手順はGitHubのリポジトリから取得して従う。"
---
<!-- scripts/memo.py build が memo.config.json から自動生成。手で編集しない -->

# cheatsheet（入口スキル）

このスキルには手順もデザイン規約も書かない。**信頼できる唯一の情報源は GitHub の `taka1156/cheatsheet` リポジトリ**。毎回そこから最新版を取得し、そこに書かれたスキルに従う。

## 使う場面

次のような依頼（言い回しは毎回違う）:

- 「〇〇を HTML で（図とともに）まとめて」「〇〇の図解ページにして」「〇〇のメモを作って」
- 「保存して」「CheatSheet に入れて」「メモに追加」
- 「さっきの説明を CheatSheet にして」
- 「〇〇をファクトチェックして」「最近のメモを事実確認して」
- そのほか CheatSheet リポジトリのページや一覧に関する作業

## 手順

### 1. リポジトリを取得する

作業用ディレクトリに浅くクローンする（すでにあれば更新）。

```bash
git clone --depth 1 https://github.com/taka1156/cheatsheet.git cheatsheet 2>/dev/null || git -C cheatsheet pull -q
```

クローンできない環境では、raw URL を WebFetch で読む（振り分けの表 → 必要なスキルの順）。

- https://raw.githubusercontent.com/taka1156/cheatsheet/master/.claude/skills/ROUTING.md
- https://raw.githubusercontent.com/taka1156/cheatsheet/master/.claude/skills/<スキル名>/SKILL.md

どちらも取得できなかったら、作り始める前にその旨を伝えて止まる。**記憶で手順や規約を再現しない。**

### 2. どのスキルを使うか決める

リポジトリの `.claude/skills/ROUTING.md` を読み、「アプリ（claude.ai）の入口スキルから使うとき」の表で依頼に合うスキルを選ぶ。表に無い依頼なら `.claude/skills/` の各 SKILL.md の description を見て選ぶ。それでも合うものが無ければ、その旨を伝えて普通に対応する。

### 3. スキルに従う

選んだスキルの `SKILL.md` を最後まで読み、その手順どおりに進める。保存するかどうか・いつ保存するかも `ROUTING.md` とスキルの記述に従う（このスキル側では決めない）。

リポジトリに書き込む手順（登録・修正・push）に進むときは、`taka1156/cheatsheet` を push 権限付きでセッションに追加してから行う。
