# MemoKit

Claude に作ってもらった図解つきの解説ページ（HTML）を、GitHub Pages で公開・蓄積するためのキットです。
このリポジトリは **テンプレートリポジトリ** なので、「Use this template」から自分のリポジトリを作って使います。

- トップページ: `docs/index.html`（メモ一覧・検索・タグ絞り込み）
- AI 向けの Markdown 版: `docs/md/` と `docs/llms.txt`（公開 URL を渡せば、リポジトリを繋いでいない会話でも Claude が過去のメモを読める）
- 設定: `memo.config.json`（サイト名・説明・リポジトリ・ブランチ・タイムゾーン・アイコンと OGP 画像。コードやスキルには直接書かない）
- 公開 URL: `docs/CNAME` があればその独自ドメイン、なければ `https://<owner>.github.io/<name>/`（`python3 scripts/memo.py url` で確認できます。OGP の URL もここから自動で決まります）

**日本語のサイト向けです。** ページの `lang="ja"`、「一覧に戻る」などの表示、`memo.py` のメッセージ、スキル（日本語で書く規約）、フォント（Noto Sans JP）は日本語前提です。

テンプレートのままの状態では、サイト名 `MemoKit`、サンプルのメモ 2 本（`docs/sample*.html`）、プレースホルダの画像が入っています。

> [!WARNING]
> **GitHub Pages で公開すると、メモはインターネット上の誰でも読めます。**
> - `docs/` のページ（各メモ・一覧）に加えて、AI 向けの Markdown 版（`docs/md/`・`llms.txt`）も公開され、検索エンジンや AI に読まれることがあります。
> - GitHub の無料プランでは Pages は公開リポジトリでしか使えないため、リポジトリ（メモの原本・コミット履歴・設定）も公開になります。
> - 「さっきの説明をメモにして」（`memo-from-chat`）は会話の内容をそのままページにします。社外秘の情報・個人情報・認証情報などを含む会話はメモにしないでください。
> - 一度公開した内容は、消してもコミット履歴やキャッシュ、第三者の保存に残ることがあります。

## はじめかた

### 1. テンプレートからリポジトリを作る

GitHub でこのリポジトリの「Use this template」→「Create a new repository」。作ったリポジトリを手元に clone します。

### 2. サンプルを消す

```bash
find docs -maxdepth 1 -name '*.html' ! -name index.html -delete   # サンプルのメモ
rm -rf docs/md docs/memos.json docs/llms.txt entry-skill            # 生成物（build で作り直す）
```

### 3. `memo.config.json` を書き換える

```json
{
  "site_name": "MyNotes",
  "description": "Claude に作ってもらった解説ページの置き場",
  "llms_description": "Claude に作ってもらった解説ページの集まり。各リンク先は本文を Markdown にしたもので、元のページへの URL も含む。",
  "repository": "alice/my-notes",
  "branch": "main",
  "utc_offset_hours": 9,
  "branding": { "accent": "#00d4ff", "accent_light": "#0077b6", "theme": "dark" }
}
```

- `repository` は自分の `owner/name`。テンプレートの値（`repo/sample`）のままだと `build` が警告します。
- `branch` はリポジトリのデフォルトブランチ（スキルの push 先）。
- 書き間違い（JSON の書式・型・範囲）は、`memo.py` を実行したときにどの項目をどう直すかを示して止まります。
- `branding` はサイト全体のアクセント色と、アイコン・OGP 画像の文字・色です。
  - `accent` はダークモード、`accent_light` はライトモードのアクセント色。全ページ（トップ・各メモ）に `build` が反映し、画像にも同じ色を使います。`accent_light` を省くと、`accent` を白地で読める濃さまで自動で暗くします。
  - `title`・`tagline`・`url`・`mark`・`theme` は画像用。空欄はサイト名・説明・公開 URL から埋まります。項目の説明は [memo-detail.md の「サイトごとの設定」](memo-detail.md#サイトごとの設定memoconfigjson) にあります。

### 4. 作り直して確かめる

```bash
python3 branding/render.py                 # アイコン・OGP 画像を設定から作り直す（要: 下の「必要なもの」）
python3 scripts/memo.py build              # 一覧・Markdown 版・入口スキルなどを生成（og:image の ?v= もここで更新）
python3 -B -m unittest discover -s tests   # テスト
```

できたファイルをコミットして push します。

### 5. GitHub の設定

- **Pages**: Settings → Pages → Source を「Deploy from a branch」、ブランチをデフォルトブランチ、フォルダを `/docs` にする。
- **Actions の書き込み権限**: Settings → Actions → General → Workflow permissions を「Read and write permissions」にする（`Build MEMO index` が生成物をコミット・push するため）。
- 独自ドメインを使うなら `docs/CNAME` にドメインを 1 行書いて push し、DNS を設定する（テンプレートには `docs/CNAME` を入れていません。無ければ `https://<owner>.github.io/<name>/` で公開されます）。

### 6. Claude から使う

- **Claude Code や、リポジトリを繋いだ claude.ai の会話**: `.claude/skills/` のスキルがそのまま使えます（下の「Claude に頼むとき」）。
- **claude.ai のアプリ**: `entry-skill/SKILL.md`（`build` が設定から生成）をアプリ側のスキルとして登録します（下の「アプリ（claude.ai）から使うとき」）。

## 必要なもの

| 用途 | 必要なもの |
| --- | --- |
| `scripts/memo.py`（登録・点検・生成）とテスト | Python 3.8 以上（標準ライブラリのみ。テストは 3.11・3.12 で確認、GitHub Actions は 3.12）、git |
| 公開 | GitHub Pages（`docs/` を公開）、GitHub Actions（生成とテスト） |
| ページの表示 | 閲覧者のブラウザが Google Fonts（`fonts.googleapis.com` の Noto Sans JP・JetBrains Mono）を読み込みます。読めないときはシステムのフォントで表示されます。メモによっては cdnjs のライブラリを使います（[memo-style](.claude/skills/memo-style/SKILL.md)） |
| `branding/render.py`（アイコン・OGP 画像の生成。設定を変えたときだけ） | `pip install playwright pillow` と `python3 -m playwright install chromium`、フォント Noto Sans CJK JP・DejaVu Sans Mono（Ubuntu なら `apt install fonts-noto-cjk fonts-dejavu-core`）。Actions では動かさないので手元で実行してコミットする |

## Claude に頼むとき

このリポジトリで作業している Claude（claude.ai でリポジトリを繋いだ会話、または Claude Code）は、`.claude/skills/` のスキルを使います。

| 言い方の例 | スキル | やること |
| --- | --- | --- |
| 「この HTML をメモに入れて」 | `memo-publish` | 崩れ修正 → タイトル・説明・タグ付け → 一覧更新 → push |
| 「〜の図解ページを作って」 | `memo-style` | デザイン規約とテンプレートに沿って新規作成 |
| 「さっきの説明をメモにして」 | `memo-from-chat` | 会話内容をページ化して登録まで |
| 「〇〇をファクトチェックして」 | `memo-factcheck` | サブエージェントで独立に事実確認 → 指摘を報告 → 確認後に修正・push |
| 「前に〜のメモ書いたよね」「〜のメモのここを直して」 | `memo-reference` | Markdown 版（`docs/md/`）で探して読む／直すときは HTML の該当箇所だけ編集 → push |
| 「memo.py を直して」「コマンドを追加して」「リファクタして」 | `memo-maintain` | テストを流す → 変更 → 出力の前後比較・テスト → memo-detail.md を更新 → push |

新しい会話では最初に「`<owner>/<name>` リポジトリで作業して」（自分のリポジトリ名）と伝えるとスキルが効きます。

## アプリ（claude.ai）から使うとき

アプリ側に置くのは「このリポジトリを取ってきて、ここのスキルに従う」だけの入口スキルです。手順やデザイン規約はすべてこのリポジトリが唯一の情報源で、アプリ側には書きません。
入口スキルの中身は `entry-skill/SKILL.md` にあり、`memo.py build` が `memo.config.json` のリポジトリ名とブランチから作ります。設定を変えたらアプリ側に貼り直してください。

入口スキルは依頼に応じて次のように振り分けます（上の表と同じ対応で、違いは保存のタイミングだけ）。

| 依頼 | 使うスキル | 保存 |
| --- | --- | --- |
| 「〇〇を HTML で（図とともに）まとめて」「図解ページにして」 | `memo-style` で作り、`memo.py preview` で 1 枚にまとめた HTML を会話内でプレビューする（`memo.py new` は使わずテンプレートをコピー） | **しない**。「保存して」と言われたら `memo-publish` で登録 |
| 「保存して」「メモに入れて」 | `memo-publish` | する |
| 「さっきの説明をメモにして」 | `memo-from-chat` | する |
| 「ファクトチェックして」 | `memo-factcheck` | 指摘を確認してもらってから修正・push |
| 「前に〜のメモ書いたよね」「メモに〜ってある？」 | `memo-reference` | しない（参照だけ） |
| 「〜のメモのここを直して」 | `memo-reference`（部分修正） | する |
| 「memo.py を直して」「仕組みを変えて」 | `memo-maintain` | テストが通ってから push |

スキルを追加したら、上の表とこの表に 1 行足せば入口スキル側の変更は不要です。

## 仕組みと memo.py

ファイルの構成（原本と生成物）、`scripts/memo.py` の各コマンド、自動生成ブロック、AI 向けの Markdown 版（`llms.txt`）、サイトごとの設定（`memo.config.json`）、表示の確認とプレビュー、GitHub Actions は、図つきで [memo-detail.md](memo-detail.md) にまとめています。

メモ（中身）と仕組みは分けてあり、仕組みは本物のメモがなくても動きます（テストは `tests/fixtures/` のサンプルで動く）。残すもの・消すものの一覧は [memo-detail.md の「このキットから始める」](memo-detail.md#このキットから始める) にあります。
