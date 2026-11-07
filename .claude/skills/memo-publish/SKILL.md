---
name: memo-publish
description: Claude が作った HTML（貼り付け・添付・アーティファクト・既存ファイル）を CheatSheet リポジトリに登録する。「CheatSheet に入れて」「チートシートに追加」「これ保存して」と言われたとき、または memo-from-chat の最後の工程で使う。崩れチェック・メタ情報付与・一覧更新・commit/push まで行う。
---

# memo-publish

HTML 1 枚を CheatSheet として登録する手順。

## 前提

- ツールは `scripts/memo.py`（標準ライブラリのみ）。**どのディレクトリから実行してもよい**。
- メモの置き場所（公開フォルダ）はスクリプトが管理する。スキル側でパスを組み立てず、**メモは名前で指定する**（例: `docker`）。実際のパスが必要なときは `memo.py path NAME` で取得する。
- 以下のコマンドは、まずリポジトリのルートに移動してから実行する。

```bash
cd "$(git rev-parse --show-toplevel)"
```

## 1. HTML を受け取る

- 貼り付け / 添付 / アーティファクト（`Artifact` の read）/ 既存ファイル、のどれか。
- **中身を最後まで読んでから**次に進む。中身を見ずに登録しない。
- 貼り付けやアーティファクトの場合は、いったん作業用の一時ファイル（スクラッチパッド）に保存する。Markdown のコードブロック（```html …```）で渡されても、手順 3 で囲いは自動で外れる。

## 2. 名前を決める

- 英小文字・数字・ハイフンの短い名前（例: `docker`, `git-rebase`, `tcp-handshake`）。`.html` は付けても付けなくてもよい。
- 内容を一言で表す英単語を選ぶ。日付や `memo-` などの接頭辞は付けない。
- `python3 scripts/memo.py list` で既存のメモを確認し、同名がある場合:
  - 同じテーマの改訂版なら、ユーザーに「上書きするか、別名にするか」を確認する。
  - 別テーマなら名前を変える。
- `index` はトップページなので使えない（スクリプトが拒否する）。

## 3. 取り込む

```bash
python3 scripts/memo.py add <受け取ったファイル> NAME          # 上書きするときは --force
```

公開フォルダに `NAME.html` として保存され、そのパスが表示される。
すでに公開フォルダ内にあるファイルなら、この手順は不要。

## 4. 崩れチェックと修正（lint）

```bash
python3 scripts/memo.py lint NAME --fix --backlink
```

自動で直すもの:
- `<style>` 内の全角クォート `‘ ’ “ ”`（コピペで化けて font-family 等が効かなくなる）
- `* {` が `- {` / `\*` に化けたもの（Markdown 経由のコピペで起きる）
- `<!DOCTYPE html>` / charset / viewport の欠落
- ページ下部フッターに「← 一覧に戻る」リンクを追加（`--backlink`）
- ファビコン・iOS アイコン・OGP の `<head>` タグ（`<!-- memo:head -->` ブロック）を追加／更新。og:title / og:description は title / description から自動で作られる

報告だけのもの（`[要対応]`）:
- JS 内の全角クォート疑い → `memo.py path NAME` のファイルを読み、文字列の区切りに使われていれば半角に直す。日本語の文中の使用ならそのまま。
- タイトル・説明・タグ・日付の欠落 → 次の手順で付ける。

ほかにも明らかな崩れ（閉じタグ欠落、Markdown 記号の混入など）に気づいたら、内容は変えずに直す。

## 5. メタ情報を付ける

中身を読んで考える。ユーザーが指定していればそれに従う。

```bash
python3 scripts/memo.py meta NAME \
  --title "Docker 動作原理" \
  --desc "イメージのレイヤー構造、名前空間、cgroups などコンテナが動く仕組みを図解。" \
  --tags "Docker,Linux" \
  --date
```

- **title**: 日本語で短く（〜20 字）。既存の `<title>` が適切ならそのまま（`--title` を省略）。
- **desc**: 何がわかるページかを 1 文（40〜60 字）。
- **tags**: 1〜3 個。表記ゆれを防ぐため、`memo.py list` に出ている既存タグに合うものがあれば再利用する（例: `Docker` と `docker` を混在させない）。
- **date**: `--date` を値なしで渡すと今日（`memo.config.json` のタイムゾーン。実行環境の時計が UTC でもずれない）。登録後は `memo.py list` で日付を確認する。
- `meta` を実行すると OGP タグも自動で更新される。`<!-- memo:head -->` 〜 `<!-- /memo:head -->` は手で編集しない。

## 6. 一覧を更新して確認

```bash
python3 scripts/memo.py lint NAME   # OK になること
python3 scripts/memo.py build       # 公開用のサイト一式を dist/ に書き出す（src/ は書き換えない）
python3 scripts/memo.py list
```

`dist/`（ページ・一覧 `memos.json`・Markdown 版）は自動生成なのでコミットも編集もしない。原本の `src/NAME.html` に自動生成ブロック（`<!-- memo:head -->`）は入れない（入っていたら lint --fix が取り除く）。

登録したページを会話内で見せるときは、ファイルをそのまま送らず `python3 scripts/memo.py preview NAME -o <スクラッチパッド>/NAME.html` で作った 1 枚版を送る（アイコン・OGP・アクセント色の自動生成ブロックが最新になる）。

## 7. commit / push

```bash
BRANCH="$(python3 scripts/memo.py config branch)"   # push 先（memo.config.json）
git fetch origin "$BRANCH"          # 遅れていれば rebase
git add -A "$(dirname "$(python3 scripts/memo.py path NAME)")"   # src/（原本）だけ。dist/ はコミットしない
git commit -m "Add memo: <タイトル>"
git push origin HEAD:"$BRANCH"
```

push すると GitHub Actions（Deploy MEMO）が build して dist ブランチにデプロイし、公開される（数分）。原本のブランチに Actions がコミットすることはない。

## 8. 報告

ユーザーには短く伝える:
- 追加した名前・タイトル・タグ
- lint で直した点（あれば 1 行で）
- 公開 URL: `python3 scripts/memo.py url NAME` の出力（独自ドメインは `src/CNAME` から決まる。URL を手で組み立てない）
