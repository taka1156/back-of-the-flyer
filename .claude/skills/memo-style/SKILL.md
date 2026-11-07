---
name: memo-style
description: MEMO リポジトリ用の解説ページ（HTML 1 枚）を新しく作るときのデザイン規約とテンプレート。「〜の図解ページを作って」「MEMO 用に解説を書いて」など、新規にメモ HTML を書くときに必ず読む。既存 HTML を登録するだけなら memo-publish を使う。
---

# memo-style

MEMO の各ページを見た目・作りの両面で揃えるための規約。
新規作成時は、リポジトリのルートで次を実行してテンプレートから作り、表示されたパスのファイルに中身を書く。

```bash
cd "$(git rev-parse --show-toplevel)"
python3 scripts/memo.py new NAME   # NAME は英小文字・ハイフン（例: git-rebase）
```

テンプレートの実体はこのフォルダの `template.html`。置き場所はスクリプトが決めるので、自分でパスを組み立ててコピーしない。

## 基本方針

- **HTML 1 枚で完結**。CSS / JS はインライン。外部は Google Fonts と、必要なら cdnjs のライブラリのみ。
- **日本語**で書く。専門用語は英語併記（例: 名前空間 (namespace)）。
- 「読む」より「見てわかる」を優先: 図（インライン SVG / CSS ボックス）、タブ切り替え、ホバーで補足、などを使う。
- スマホ幅（〜380px）で横スクロールが出ないこと。左右 16px 以上の余白。

## デザイントークン

トップページ（メモ一覧）と揃える。`:root` に変数で定義し、ダークモードは `prefers-color-scheme` で切り替え。

| 変数 | ライト | ダーク | 用途 |
| --- | --- | --- | --- |
| `--bg` | `#f6f7f9` | `#0a0e14` | 背景 |
| `--surface` | `#ffffff` | `#111823` | カード・パネル |
| `--fg` | `#1c2230` | `#cdd9e5` | 本文 |
| `--fg-2` | `#5a6376` | `#7d8b9d` | 補足文字 |
| `--line` | `#dde1e8` | `#1e2d3d` | 罫線 |
| `--accent` | `#0077b6` ※ | `#00d4ff` ※ | 見出し・強調・リンク |
| `--chip` | `#eceff4` | `#18222f` | タグ・ボタン背景 |

※ `--accent` はサイトの設定（`memo.config.json` の `branding.accent_light`・`branding.accent`）で決まり、`build` が `dist/` に書き出すページで自動生成ブロック（`memo:head`）が値を上書きする。ページには表の値を書いておけばよく、色を自分で変えない。アクセント色が要る箇所は必ず `var(--accent)` を使い、色の値を直接書かない（`rgba()` で薄めたいときは `color-mix(in srgb, var(--accent) 20%, transparent)`）。

図の中で色分けが必要なときは、意味ごとに追加変数を定義する（例: `--c-ok`, `--c-warn`）。色だけで意味を伝えず、ラベルも付ける。

- 本文フォント: `'Noto Sans JP', system-ui, sans-serif`
- 見出し・コード・数値: `'JetBrains Mono', ui-monospace, monospace`
- 本文 15px 前後、行間 1.7。最大幅 880px で中央寄せ。

## ページ構成

1. `h1` タイトル（アクセント色、等幅フォント）＋ 1 行のサブタイトル
2. 要点（3 行程度の「ざっくり言うと」）
3. 本体: 図解・タブ・ステップ。セクションは `h2` で区切る
4. 必要なら「よくある誤解」「コマンド例」
5. ページ下部フッターの「← 一覧に戻る」リンク（`index.html` へ。テンプレートに含まれている。固定表示のボタンにはしない）

## メタ情報（必須）

`<head>` に入れる。memo-publish の `memo.py meta` で後から付けてもよい。

```html
<title>Docker 動作原理</title>
<meta name="description" content="何がわかるページかを 1 文で">
<meta name="memo:tags" content="Docker, Linux">
<meta name="memo:date" content="YYYY-MM-DD">
```

アイコン（ファビコン・iOS）と OGP のタグは `memo.py` が `<!-- memo:head -->` ブロックとして自動で入れるので、自分では書かない。

## 崩れ防止（コピペ事故対策）

- CSS / JS の引用符は必ず半角 `'` `"`。全角 `‘’“”` は font-family が効かなくなる原因。
- セレクタ `*` を行頭に置くとき、Markdown 経由で `-` や `\*` に化けないよう、ファイルとして直接保存する。
- 書いたら `python3 scripts/memo.py lint NAME` で確認する。

## 会話内でプレビューするとき

`preview` で自動生成ブロック（アイコン・OGP・アクセント色）を入れた 1 枚を作って送る（公開版と見た目・動きは変わらない）。下書きのファイルパスにも使える。

```bash
python3 scripts/memo.py lint 下書き.html --fix --backlink           # 崩れを直す（自動生成ブロックは preview・build が入れる）
python3 scripts/memo.py preview 下書き.html -o <スクラッチパッド>/NAME.html
```

送るのは preview の出力。保存（memo-publish）するときは元の下書きを使う。

## 書き終えたら

memo-publish の手順 4 以降（lint → meta → build → commit/push → 報告）で登録する（`new` で作ったので取り込み手順 3 は不要）。
