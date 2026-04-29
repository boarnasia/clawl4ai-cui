# task2: 基盤実装（スクレイプコマンド）

## 参照

- 基本設計: [docs/basic-design.md](../../docs/basic-design.md)
- 詳細仕様: [task/task1/index.md](../task1/index.md)

## 目的

task3（管理コマンド）が依存する基盤をすべてこのタスクで完成させる。
task2 完了後、`python main.py <url>` が動作する状態になること。

## やること

### 1. 依存ライブラリの追加

`pyproject.toml` に `structlog` を追加する。

### 2. ロガーの初期化（`logger.py` または `main.py` 内）

- structlog を JSON フォーマットで設定する
- 出力先: `var/logs/app.log`（ディレクトリ未存在時は自動作成）
- ローテーション: 10MB × 5世代
- タイムスタンプ: UTC ISO 8601
- 全エントリに `timestamp` / `level` / `event` / `command` を含む

### 3. DB の初期化（`db.py` または `main.py` 内）

- `sqlite.db` を作成し `scrape_history` テーブルを生成する（なければ作成）
- スキーマ: `id` / `url` / `file_path` / `scraped_at`

### 4. ファイル名変換ロジック

URL とページタイトルから保存ファイル名を生成する関数を実装する。
変換規則は [task/task1/index.md](../task1/index.md) の「変換ルール」セクションを参照。

### 5. スクレイプコマンドの実装

`python main.py <url>` を実装する。

処理フロー:
1. `command_start` をログ出力
2. `download/` ディレクトリを自動作成
3. crawl4ai で URL をスクレイプ
4. 結果が空なら `scrape_empty` を warning ログ → 終了コード 1
5. ページタイトルを取得してファイル名を生成
6. `download/<ファイル名>` に Markdown を保存（上書き）
7. `scrape_history` に UPSERT（新規なら `db_insert`、更新なら `db_upsert`）
8. `command_end` をログ出力

### 6. 引数パース・エラーハンドリング

- 引数なし、不正な引数の場合は使用方法を stderr に出力して終了コード 1
- URL アクセス失敗は `scrape_failed` を error ログ → stderr にメッセージ → 終了コード 1

## 完了条件

- `python main.py https://code.claude.com/docs/en/` を実行すると `download/` にファイルが保存される
- `sqlite.db` にレコードが登録される
- `var/logs/app.log` に JSON ログが出力される
- 再実行しても正常動作する（UPSERT・上書き保存）
