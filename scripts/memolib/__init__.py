"""scripts/memo.py の中身。

- config:   置き場所・公開 URL・日付などの設定
- meta:     メモのメタ情報の読み書きと、名前からパスへの解決
- blocks:   自動生成ブロック（memo:head・memo:quiz）・フッター・クイズの問題データ
- lint:     崩れのチェックと自動修正
- markdown: AI 向けの Markdown 版
- site:     memos.json・quizzes.json と、会話内プレビュー用の 1 枚の HTML

コマンド（scripts/memo.py）以外から使うときも、ファイルを書き換えるのは各関数の呼び出し側。
多くの関数は文字列を受け取って文字列を返すだけなので、テストしやすい。
"""
