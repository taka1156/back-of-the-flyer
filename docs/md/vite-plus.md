<!-- scripts/memo.py build が自動生成。手で編集しない -->

# Vite+ と vp コマンド チートシート

> Vite・Vitest・Oxlint などを 1 つにまとめた Vite+ の機能と、vp コマンドの使い方を用途別に一覧にしたチートシート。

- URL: https://repo.github.io/sample/vite-plus.html
- タグ: Vite, JavaScript, ツール
- 日付: 2026-11-07

---

# Vite+ / vp チートシート

Web 開発のツール一式を 1 つの `vp` コマンドにまとめた Vite+ の機能と使い方

**ざっくり言うと**

- Vite・Rolldown・Vitest・tsdown・Oxlint・Oxfmt・Vite Task を `vp` 1 つから使う統合ツールチェーン（MIT ライセンス）
- Node.js とパッケージマネージャー（pnpm / npm / yarn / bun）の版も自動で管理する
- 設定は `vite.config.ts` 1 つにまとめる（lint・fmt・test・pack・タスクも同じファイル）

## 構成：vp の下で何が動くか

vp 1 つの CLI ＋ vite.config.ts 1 つ

↓ コマンドごとに中のツールを呼ぶ

**vp dev / build / preview** Vite ＋ Rolldown

**vp test** Vitest

**vp lint** Oxlint

**vp fmt** Oxfmt

**vp check** Oxfmt ＋ Oxlint ＋ 型チェック（tsgo）

**vp pack** tsdown ＋ Rolldown

**vp run** Vite Task（キャッシュ付きタスク実行）

**vp install / add …** pnpm・npm・yarn・bun を自動で選ぶ

↓ 実行環境

**vp env** … Node.js とパッケージマネージャーの版を管理（プロジェクトごとに固定できる）

## 主な機能

### 開発とビルド

Vite と Rolldown がベース。HMR、大きなアプリ向けの全体バンドル開発モード（オプトイン）、Vite のプラグインがそのまま使える。

### チェック

`vp check` でフォーマット・lint・型チェックを一度に。Prettier 互換のフォーマット、ESLint 互換のルール 750 以上、型情報を使う lint。

### テスト

Vitest がベース。Jest 互換の API、既定でテストを分離、ブラウザモード、カバレッジ、スナップショット、型テスト。import は `vite-plus/test` から。

### タスク実行

`vp run` がワークスペース全体の依存の順にタスクを実行し、結果をキャッシュ。入力ファイル・引数・指定した環境変数が同じなら実行を飛ばして出力を再生する。

### ライブラリのパッケージ化

`vp pack` で型定義の生成、package.json の exports の自動生成、単体の実行ファイル、バンドルしない変換だけのモード。

### 環境の管理

Node.js とパッケージマネージャーをプロジェクトに合わせて自動で使い分ける。 `vp env pin` で版を固定、 `vp env off` で管理をやめられる。

### Git フック

`vp config` でフックを入れ、 `vp staged` でステージしたファイルだけチェック。lint-staged の代わりになる。

### フレームワーク

React・Vue・Svelte・Solid など Vite ベースのもの、メタフレームワーク、Nitro、Vercel・Netlify・Cloudflare などで使える。

## vp コマンド チートシート

セットアップ

パッケージ

開発・ビルド

チェック・テスト

タスク・キャッシュ

環境・Git フック

| コマンド | やること |
| --- | --- |
| `curl -fsSL https://vite.plus \| bash` | グローバル CLI を入れる（macOS / Linux）。入れたら新しいシェルで `vp help` |
| `irm https://vite.plus/ps1 \| iex` | グローバル CLI を入れる（Windows PowerShell） |
| `vp` | 引数なしで対話式のメニューを開く |
| `vp create` | 対話式で新しいアプリ・パッケージ・モノレポを作る |
| `vp create vite:application` | 組み込みテンプレート（ `vite:monorepo` / `vite:application` / `vite:library` / `vite:generator` ） |
| `vp create vite -- --template react-ts` | `--` の後ろはテンプレート側に渡る |
| `vp create --list` | 使えるテンプレートを表示 |
| `vp create … --no-interactive --package-manager pnpm` | 質問なしで作る。 `--directory` ・ `--no-git` ・ `--no-hooks` ・ `--agent` ・ `--editor` も指定できる |
| `vp migrate` | 今のプロジェクトを Vite+ に移行（依存・import・設定・スクリプトを書き換えてフォーマット） |
| `vp migrate --no-interactive` | 質問なしで移行。モノレポはワークスペースのルートで実行 |
| `vp migrate --agent claude --editor zed` | 移行時にエージェント用の指示ファイルとエディタ設定も書く |
| `pnpm exec vp check` | グローバル CLI を入れず、プロジェクトの vite-plus 経由で使う |

| コマンド | やること |
| --- | --- |
| `vp install` | package.json とロックファイルどおりに入れる（パッケージマネージャーは自動で選ばれる） |
| `vp install --frozen-lockfile` | ロックファイルの変更が必要なら失敗させる（CI 向け） |
| `vp install --filter web` | モノレポの一部だけ。 `-w` はワークスペースのルート |
| `vp add react` | `dependencies` に追加 |
| `vp add -D typescript vitest` | `devDependencies` に追加。 `--save-peer` で peer に |
| `vp remove react` | 削除。 `--filter web` で特定のパッケージから |
| `vp update` | 依存を新しい版に。 `vp outdated` で更新できるものを表示 |
| `vp dedupe` | 重複した依存をまとめる |
| `vp why react` | なぜ入っているかを表示 |
| `vp info react` | レジストリの情報（版・dist-tag）を表示 |
| `vp list` | 入っているパッケージ。 `-g` でグローバル |
| `vp pm audit --json` | `vp pm <command>` で使っているパッケージマネージャーのコマンドをそのまま実行 |

| コマンド | やること |
| --- | --- |
| `vp dev` | Vite の開発サーバーを起動（HMR） |
| `vp build` | 本番ビルド。 `--watch` ・ `--sourcemap` |
| `vp preview` | `vp build` の結果をローカルで配信して確かめる |
| `vp pack` | ライブラリをビルド（tsdown） |
| `vp pack src/index.ts --dts` | 型定義（.d.ts）も出す |
| `vp pack --watch` | 変更を見て作り直す |
| `vp pack --exe` | 単体で動く実行ファイルを作る（Node.js 25.7.0 以上。 `vp env use 26` ） |

| コマンド | やること |
| --- | --- |
| `vp check` | フォーマット → lint → 型チェックをまとめて実行 |
| `vp check --fix` | フォーマットと自動修正をかける（ファイルが変わる） |
| `vp check --deny-warnings` | lint の警告もエラー扱い。 `--quiet` で警告を隠す |
| `vp check --no-fmt --no-lint` | 型チェックだけ（ `typeAware` と `typeCheck` が有効なとき） |
| `vp check --fix src/index.ts` | オプションはファイルパスより前に書く |
| `vp lint` | Oxlint だけ実行。 `--fix` ・ `--type-aware` |
| `vp fmt` | Oxfmt でフォーマット。 `--check` で確認だけ |
| `vp test` | Vitest を 1 回だけ実行（既定ではウォッチしない） |
| `vp test watch` | ウォッチモードで実行 |
| `vp test run --coverage` | カバレッジ付きで実行 |
| `vp staged` | ステージしたファイルにだけチェック（設定は `staged` ）。 `--fail-on-changes` |

| コマンド | やること |
| --- | --- |
| `vp run build` | タスク（vite.config.ts の `run.tasks` か package.json の scripts）を実行。省略形 `vpr build` |
| `vp run -r build` | 全ワークスペースで依存の順に実行 |
| `vp run -t @my/app#build` | そのパッケージと依存先だけ |
| `vp run --filter "@my/*" --filter "!@my/utils" build` | 名前・glob・ディレクトリで選ぶ。 `!` で除外、 `...` で依存も含める |
| `vp run -w build` | ワークスペースのルートで実行 |
| `vp run --cache build` | package.json の scripts もキャッシュする（既定はしない） |
| `vp run --no-cache build` | 今回だけキャッシュを使わない |
| `vp run -r --parallel dev` | 依存を無視して全部同時に起動 |
| `vp run -r --concurrency-limit 8 build` | 同時実行数（既定 4） |
| `vp run -r -v build` | 詳しい実行結果を表示。 `--last-details` で前回分 |
| `vp run test --reporter verbose` | タスク名の後ろの引数はコマンドに渡る |
| `vp cache clean` | タスクのキャッシュ（node_modules/.vite/task-cache）を消す |
| `vp exec tsc --noEmit` | プロジェクトに入っているコマンドを実行（ダウンロードしない） |
| `vpx eslint .` | 手元にあれば使い、無ければ取ってきて実行（npx 相当。TS ファイルも実行できる） |
| `vp dlx create-vite` | 毎回ダウンロードして 1 回だけ実行 |

| コマンド | やること |
| --- | --- |
| `vp env setup` | Node.js とパッケージマネージャーの切り替え用シム・シェル設定を作る |
| `vp env pin lts pnpm@10` | プロジェクトの版を固定（.node-version・packageManager などに書く） |
| `vp env use 20 pnpm@10` | 今のシェルだけ版を切り替え。 `--unset` で戻す |
| `vp env install` | 固定した版を入れる |
| `vp env default lts` | グローバルの既定の版 |
| `vp env current --json` | 今どの版が使われているか |
| `vp env which node` | 実際に使われるコマンドのパス |
| `vp env list-remote --lts` | 入れられる版の一覧 |
| `vp env doctor` | 環境の診断 |
| `vp env off` | Vite+ の管理をやめてシステムの Node.js などを優先（ `vp env on` で戻す） |
| `vp node -e "console.log(1+1)"` | 解決された Node.js で実行 |
| `vp toolchain` | プロジェクトで使っているツールの版を表示（ `--global` でグローバル） |
| `vp config` | Git フックとエージェント連携をセットアップ。 `--no-hooks` ・ `--no-agent` |
| `vp hooks status` | フックの状態。 `enable` / `disable` |
| `vp upgrade` | グローバルの vp を更新。 `--check` ・ `--rollback` ・ `vp upgrade <version>` |
| `vp implode` | グローバルの Vite+ と関連データを削除 |

組み込みコマンド（ `dev` ・ `build` ・ `test` など）は package.json の同名スクリプトでは上書きできない。スクリプトの方を動かすときは `vp run dev` 。

（元のページで操作できます → https://repo.github.io/sample/vite-plus.html#cheatsheet）

## 設定：vite.config.ts 1 つにまとめる

```
import { defineConfig } from 'vite-plus';

export default defineConfig({
  server: {},             // Vite の開発サーバー（build・preview も同じ）
  lint: {                  // Oxlint
    ignorePatterns: ['dist/**'],
    options: { typeAware: true, typeCheck: true },  // vp check で型チェックもする
  },
  fmt: { singleQuote: true },          // Oxfmt
  check: { fmt: false },               // vp check でフォーマットを飛ばす（任意）
  test: { include: ['src/**/*.test.ts'] },  // Vitest
  pack: { dts: true, format: ['esm', 'cjs'] }, // tsdown
  staged: { '*': 'vp check --fix' },   // vp staged（コミット前）
  run: {                   // Vite Task
    tasks: {
      build: { command: 'vp build', dependsOn: ['lint'], cache: { env: ['NODE_ENV'] } },
      deploy: { command: 'deploy-script --prod', cache: false, dependsOn: ['build', 'test'] },
    },
  },
});
```

`vitest.config.ts` ・ `.oxlintrc.json` ・ `.oxfmtrc.json` ・ `tsdown.config.ts` を別に置くのは推奨されていない。 `defaultPackage: './frontend'` で、引数なしの `vp dev` などの対象ディレクトリを決められる。

## よくある誤解

**「vp test はウォッチし続ける」** → Vitest 単体と違い、 `vp test` は 1 回実行して終わる。ウォッチは `vp test watch` 。

**「vp dev で package.json の dev スクリプトが動く」** → `vp dev` は常に組み込みの Vite 開発サーバー。スクリプトは `vp run dev` 。

**「package.json の scripts も自動でキャッシュされる」** → 既定でキャッシュされるのは vite.config.ts の `run.tasks` だけ。scripts は `vp run --cache` が必要。同じ名前のタスクを両方に書くことはできない。

**「環境変数が変わればキャッシュは無効になる」** → キャッシュのキーになるのは `cache.env` に書いた変数だけ。ビルド結果が変わる変数は書いておく。

**「vp upgrade でプロジェクトの Vite+ も上がる」** → `vp upgrade` はグローバルの `vp` だけ。プロジェクトの `vite-plus` は別に更新する（ `vp toolchain` で版を確認）。

## 出典

[viteplus.dev](https://viteplus.dev/) ・ [Getting Started](https://viteplus.dev/guide/) ・ [Config](https://viteplus.dev/config/) ・ [Run](https://viteplus.dev/guide/run) ・ [Cache](https://viteplus.dev/guide/cache) ・ [Env](https://viteplus.dev/guide/env) ・ [vpx](https://viteplus.dev/guide/vpx) （2026-11-07 時点）
