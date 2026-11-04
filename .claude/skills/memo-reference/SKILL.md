---
name: memo-reference
description: MEMO の既存メモを参照・検索・部分修正するときに使う。「前に〜のメモ書いたよね」「MEMO に〜ってある？」「〜のメモを踏まえて説明して」「〜のメモのこの部分を直して」など。HTML ではなく Markdown 版（docs/md/）を読み、直すときは HTML の該当箇所だけを読んで編集する。
---

# memo-reference

既存のメモを読むときは **Markdown 版** を使う。HTML は CSS・SVG・JS 込みで本文の 3〜4 倍の重さがあるので、読むためだけに開かない。
直すときは HTML が元データなので HTML を編集するが、ファイル全体ではなく**該当箇所だけ**を読む。

## 前提: Markdown 版とは

`python3 scripts/memo.py build` が HTML から自動生成する（手で編集しない。次の build で上書きされる）。

| ファイル | 中身 |
| --- | --- |
| `docs/llms.txt` | 全メモの目次。タイトル・説明・タグ・日付と、各 Markdown 版へのリンク |
| `docs/md/NAME.md` | 1 本のメモ。冒頭にタイトル・説明・元ページの URL・タグ・日付、続けて本文 |

本文の読み方:

- `（図: A / B / C → URL#id）` … SVG の図。ラベルと、図がある節へのリンク
- `（元のページで操作できます → URL#id）` … ボタンやチェックボックスなど、触って動くパーツがある節
- `## ページ内のデータ（JavaScript で描画される部分）` … 本文を JS で描画するページは、スクリプトをそのまま載せている
- **入っていないもの**: JS の中にだけある文章（タップで出る説明文など）。必要なときだけ HTML の `<script>` を見る

## 1. 探す

```bash
cd "$(git rev-parse --show-toplevel)"
```

- まず `docs/llms.txt` を読む（全体で十数 KB）。タイトル・説明・タグで当たりをつける。
- 言葉で探すなら `docs/md/` を Grep する（`-n` で行番号つき）。言い回しが違いそうなら、同義語・英語表記でも探す。
- 見つからなければ「MEMO にはない」と伝える。似たメモがあればそれを挙げる。

## 2. 読む

- `python3 scripts/memo.py path NAME --md` のファイルを読む。HTML は開かない。
- 長いメモで一部だけ必要なら、Grep で見出し（`^## `）の行番号を出し、その節だけ読む。
- Markdown 版が古い疑いがあるとき（HTML を手元で編集した直後など）は、先に `python3 scripts/memo.py build` を実行する。`build --check` で最新か確かめられる。

HTML を読むのは次のときだけ:

- JS の中にだけある文章が必要なとき
- 見た目・レイアウト・動きについて聞かれたとき
- 修正するとき（下の 4.）

## 3. 答える・案内する

- メモの内容を自分の言葉でまとめて答え、どのメモに基づくかを示す。Markdown 版をそのまま貼らない。
- 図が説明の助けになる箇所では、Markdown 版の `→ URL#id` のリンクを添えて「図はここ」と案内する。MEMO の売りは図解なので、文章で説明しきろうとせず元ページに誘導してよい。
- メモの記述が古そう・怪しいと気づいたら、答えとは別にそう伝える（直すかどうかはユーザーに聞く）。

## 4. 部分修正

1. **場所を特定する**: Markdown 版で直す箇所と、その節の見出しを見つける。
2. **HTML の該当箇所だけ読む**: `python3 scripts/memo.py path NAME` の HTML を、見出しの id（`id="overlayfs"` など。Markdown 版のリンクの `#` 以降）か、直したい文言そのもので Grep（`-n`）する。ヒットした行の前後だけを Read の offset / limit で読む（目安 50〜100 行）。
3. **該当部分だけ書き換える**: Edit で文字列を置き換える。ファイル全体を書き直さない。構成・デザイン・クラス名は変えない。
4. 次の場合は HTML 全体を読んでよい: デザインやレイアウトの崩れを直す、構成を組み替える、JS で動く部分を直す、複数の節にまたがって直す。
5. **反映する**:

```bash
python3 scripts/memo.py lint NAME      # OK になること
python3 scripts/memo.py build          # 一覧と Markdown 版を更新
BRANCH="$(python3 scripts/memo.py config branch)"   # push 先（memo.config.json）
git fetch origin "$BRANCH"              # 遅れていれば rebase
git add -A "$(dirname "$(python3 scripts/memo.py path NAME)")"
git commit -m "Update memo: <タイトル>"
git push origin HEAD:"$BRANCH"
```

- `memo:date` は更新しない（作成日のまま）。タイトルや説明が変わる修正なら `memo.py meta` で直す。
- 報告は短く: 何を直したか、公開 URL（`python3 scripts/memo.py url NAME`）。
