---
name: memo-maintain
description: CheatSheet リポジトリの Python スクリプト（scripts/memo.py・scripts/memolib/・tests/）やトップ・ロードマップページの JS、GitHub Actions を直すときの手順。「memo.py を直して」「コマンドを追加して」「リファクタして」「テストを足して」などで使う。メモの作成・登録・参照には使わない（memo-style / memo-publish / memo-reference）。
---

# memo-maintain

CheatSheet の仕組みそのもの（スクリプト・共通ファイル・ワークフロー）を変えるときの手順。
仕組みの全体像は `memo-detail.md`（リポジトリ直下）が唯一の説明書なので、**まずそこを読み、最後にそこを更新する**。

## 守ること

- **標準ライブラリだけ。** pip で何かを入れないと動かない形にしない（BeautifulSoup・pytest なども使わない。テストは `unittest`）。
- **入口は `python3 scripts/memo.py` のまま。** スキル・README・Actions がこの呼び方に依存している。処理の本体は `scripts/memolib/` に置き、`memo.py` はコマンドの受け付けだけにする。
- **置き場所を知っているのは `memolib/config.py` だけ。** 他のモジュールやスキルでパスを組み立てない。
- **サイトごとの値は `memo.config.json` だけ。** サイト名・リポジトリ・ブランチ・タイムゾーン・ドメインを、コード・スキル・ワークフロー・`index.html`・`roadmap.html` に直接書かない（ページには `data-memo-site` の目印を付けて `build` に入れさせる。スキルは `memo.py config KEY` で読む）。仕組みだけを別のリポジトリに持っていけるようにするため。
- **テストは本物のメモに頼らない。** 新しいテストは `tests/fixtures/` のサンプル（`Workspace()`）で書く。本物のメモを確かめるものだけ `RepositoryTest` に置く（メモがないと飛ばされる）。
- **原本は `src/`、生成物は `dist/`。** `build` は `src/` を読むだけで書き換えず、公開するサイト一式（自動生成ブロック入りのページ・`memos.json`・`md/`・`llms.txt`・入口スキル）を `dist/` に書き出す。生成物を手で直さず、生成する側を直して `build` する。`dist/` はコミットしない（`.gitignore` 済み）。
- **何度実行しても同じ結果になる。** lint・build・meta を 2 回続けて実行しても 2 回目は何も変わらないこと。`dist/` を消して build し直しても同じ中身になること（テストで確かめている）。
- **自動生成ブロックの目印（`<!-- memo:head` など）と `data-memo-site` の書き方は変えない。** 既存のページがその目印で見つけられている。

## モジュールの役割

| ファイル | 役割 |
| --- | --- |
| `scripts/memo.py` | コマンドの受け付け（`cmd_*` と `main`）だけ |
| `memo.config.json` | サイトごとの値（サイト名・説明・リポジトリ・ブランチ・タイムゾーン） |
| `memolib/config.py` | 置き場所（原本の `src/`・出力の `dist/`）・`memo.config.json` の読み込み・公開 URL・日付・アクセント色の計算・自動生成ブロックの目印 |
| `memolib/meta.py` | `<head>` のメタ情報の読み書き、名前からパスへの解決 |
| `memolib/blocks.py` | 自動生成ブロック（memo:head）、サイト設定の差し込み（`apply_site`）、フッター、廃止したクイズの片付け（`strip_quiz`） |
| `memolib/entry.py` | アプリ側の入口スキル（`dist/entry-skill/SKILL.md`）の中身 |
| `memolib/lint.py` | 崩れのチェックと自動修正 |
| `memolib/markdown.py` | AI 向けの Markdown 版 |
| `memolib/site.py` | memos.json、会話内プレビュー用の 1 枚の HTML |
| `memolib/dist.py` | `dist/` に置く全ファイルを組み立てて書き出す（`src/` のコピー＋生成物。消えたファイルは `dist/` からも消す。オプションのページはオンのときだけ） |
| `tests/test_cli.py` | コマンドを外から動かす結合テスト（作りを変えても通るもの）。`RepositoryTest` だけ本物のメモを見る |
| `tests/test_units.py` | 関数ごとの単体テスト |
| `tests/snapshot.py` | 全コマンドの出力をフォルダに保存する（前後比較用。本物のメモがなければサンプルで） |
| `tests/fixtures/` | テスト用のサンプルのメモ 2 本と設定 |

モジュール同士の依存は `config ← meta ← blocks ← lint / markdown / site ← dist ← memo.py`（と `config ← entry ← dist`）の一方向。逆向きの import を作らない。

## 手順

### 1. 始める前

```bash
cd "$(git rev-parse --show-toplevel)"
python3 -B -m unittest discover -s tests      # 全部通ることを先に確かめる（15 秒ほど）
```

通らなければ、変更を始める前にその原因を伝える。

### 2. 変更の種類で分ける

**A. 出力を変えないもの（リファクタリング・整理・高速化）**

前後の出力が 1 バイトも変わらないことを確かめる。

```bash
python3 -B tests/snapshot.py <スクラッチパッド>/before    # 変更の前に
# … 変更する …
python3 -B tests/snapshot.py <スクラッチパッド>/after     # 変更の後に
diff -r <スクラッチパッド>/before <スクラッチパッド>/after   # 何も出なければ OK
```

差分が出たら、それが意図したものでない限り直す。

**B. 出力を変えるもの（機能追加・不具合修正・見た目の変更）**

1. 先にテストを足す・直す（不具合なら、それを再現するテストが失敗することを確かめてから直す）。
2. 実装する。
3. `python3 -B scripts/memo.py build` で `dist/` を作り直し、出力の「追加・変更・削除」の数が想定どおりかを見る。全ページが変わる変更（memo:head・Markdown 変換）は、その旨をユーザーに伝えてからコミットする。
4. ページの見た目や動きに関わる変更は、build してからブラウザで確かめる（`python3 -m http.server -d dist` と、会話に見せるなら `memo.py preview`）。

### 3. 仕上げの確認

```bash
python3 -B -m unittest discover -s tests          # 全部通る
python3 -B scripts/memo.py build && git status --short   # dist/ を作り直しても src/ に差分が出ない
python3 -B -m py_compile scripts/memo.py scripts/memolib/*.py tests/*.py
```

GitHub Actions は Python 3.12 で動く。手元に `python3.12` があればそれでもテストを流す。
`-B` を付けて `__pycache__` を作らない（`.gitignore` 済みだが、作業ツリーを汚さない）。

### 4. ドキュメントを合わせる

変えた内容に応じて、次を更新する。

| 変えたもの | 更新する場所 |
| --- | --- |
| コマンド・オプション | `memo.py` 冒頭の使い方、`memo-detail.md` のコマンド一覧と詳細、それを使うスキル |
| 生成物・自動生成ブロック・データの流れ | `memo-detail.md` の該当する図と表 |
| モジュールの分け方 | `memo-detail.md`、このスキルの「モジュールの役割」 |
| ワークフロー | `memo-detail.md` の「GitHub Actions」 |
| 設定の項目 | `memolib/config.py` の `DEFAULTS`、`memo-detail.md` の「サイトごとの設定」、テストの `tests/fixtures/memo.config.json` |
| 仕組みとして残すファイル | `memo-detail.md` の「このキットから始める」、`tests/helpers.py` の `MECHANISM_DOCS` |
| スキルの追加 | README の 2 つの表に 1 行ずつ |

`memo-detail.md` の Mermaid の図を変えたら、描画できることを確かめる（構文エラーだと GitHub で図が出ない）。

### 5. コミット

- コミットするのはスクリプトと原本だけ。生成物（`dist/`）はコミットしない。
- push すると `Test memo.py`（テスト）と `Deploy MEMO`（build して dist ブランチにデプロイ）の 2 つのワークフローが動く。

## 過去につまずいたこと

- **日付**: 実行環境の時計は UTC のことがある。「今日」は `config.today()`（`memo.config.json` のタイムゾーン）を使う（`date.today()` を使わない）。
- **埋め込みの閉じタグ**: JS や JSON を `<script>` に埋め込むときは `</script` をエスケープする（`window.MEMO_DATA`）。
- **共通ファイルとプレビュー**: トップページとロードマップは `memos.json` を読み込む。HTML 1 枚だけを渡す場面では動かないので、会話に見せるときは `memo.py preview` を通す。
- **Actions の差分検出**: `git diff` は新しく生成された（未追跡の）ファイルを見ない。`git status --porcelain` を使う。
