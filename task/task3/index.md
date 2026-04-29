# task3: 管理コマンド（list / update / delete）

## 参照

- 基本設計: [docs/basic-design.md](../../docs/basic-design.md)
- 詳細仕様: [task/task1/index.md](../task1/index.md)

## 前提

task2 が完了していること（ロガー・DB・スクレイプ基盤が動作する状態）。

## 目的

スクレイプ済みデータの管理コマンドをすべて実装する。
task3 完了後、全コマンドが動作する状態になること。

## やること

### 1. `list` コマンド

`python main.py list`

- `scrape_history` を `scraped_at` 昇順で全件取得
- 標準出力に `<scraped_at>\t<url>\t<file_path>` を1行1件で出力
- `list_output` をログ出力（`count` フィールドあり）

### 2. `update` コマンド

`python main.py update`

- `scrape_history` を `scraped_at` 昇順で全件取得し、順に再スクレイプ
- 各URLの処理は task2 のスクレイプフローと同じ（`command_start` / `command_end` は全体で1回）

`python main.py update <url>`

- 指定URLが DB に存在しなければ `url_not_found` を error ログ → stderr → 終了コード 1
- 存在すれば task2 のスクレイプフローで再取得

### 3. `delete` コマンド

`python main.py delete <url>`

- 指定URLが DB に存在しなければ `url_not_found` を error ログ → stderr → 終了コード 1
- `download/<file_path>` を削除
- `scrape_history` からレコードを削除
- `db_delete` をログ出力

`python main.py delete --all`

- 件数を取得して `Delete all N entries? [y/N]: ` を表示
- `y` 以外は `delete_all_cancelled` をログ出力して中断
- `y` なら全ファイルを削除 → 全レコードを削除 → `db_delete_all` をログ出力（`count` フィールドあり）

## 完了条件

- `python main.py list` でスクレイプ済み一覧が出力される
- `python main.py update` で全URLが再スクレイプされる
- `python main.py update <url>` で指定URLが再スクレイプされる
- `python main.py delete <url>` でファイルとレコードが削除される
- `python main.py delete --all` で確認後に全件削除される
- 存在しないURLを指定した場合は終了コード 1 で終了する
