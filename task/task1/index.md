# ai向けのスクレイピングツールを作る

## 仕様

### input

`python main.py <url>`

- url: スクレイピングしたいURL（起点ページ）

### クロール動作

- 指定 URL を起点に、**同一 URL プレフィックス配下**のページを再帰的（BFS）に全取得する
- 例: `https://code.claude.com/docs/en/` を指定すると `https://code.claude.com/docs/en/` 以下のページをすべて取得する
- 外部ドメインへのリンクは辿らない
- 取得済みページは再訪問しない

### output

`download` ディレクトリに **起点URLごとに1ファイル** 保存する

#### `url` が `https://code.claude.com/docs/en/` のケース

ファイル名: `code.claude.com_docs_en.md`

変換ルール（URLパート）

- `https://` `http://` などのプロトコル部分は除去する
- `.` ドットはそのまま
- `/` スラッシュは `_` に変換する
- 末尾の `/` は除去してから変換するため、末尾に `_` は付かない
- ` ` スペースは `_` に変換する
- パスとして扱えない文字（`?` `#` `&` `=` `*` `"` `<` `>` `|` `\` `:`）は `_` に変換する

変換ルール（ファイル名全体）

- URL変換後の文字列をそのままファイル名に使う
- 拡張子は `.md`
- 同一URLを再度スクレイプした場合は上書き保存する

ファイル内容

- crawl4ai が生成した Markdown を複数ページ分マージして保存する（各ページ本文は `<!-- source: ... -->` 区切りで連結）

### 副作用

#### SQLite DB

- スクレイプしたURLは `sqlite.db`（プロジェクトルート直下）に保存する
- テーブル名: `scrape_history`
- スキーマ:

| カラム名    | 型       | 説明                                 |
|-------------|----------|--------------------------------------|
| id          | INTEGER  | PRIMARY KEY AUTOINCREMENT            |
| url         | TEXT     | スクレイプしたURL（UNIQUE制約あり）  |
| file_path   | TEXT     | 保存先ファイルパス（downloadディレクトリからの相対パス）|
| scraped_at  | TEXT     | 最終スクレイプ日時（ISO 8601形式、UTC）|

- 同一URLを再スクレイプした場合は `url` で UPSERT（file_path・scraped_at を更新）

#### `list` コマンド

`python main.py list`

- 標準出力に1行1レコードで出力する
- 出力フォーマット: `<scraped_at>\t<url>\t<file_path>`
- 例: `2026-04-29T10:00:00Z	https://code.claude.com/docs/en/	code.claude.com_docs_en.md`
- ソート順: `scraped_at` 昇順
- フィルタリングは grep などで行うので不要

#### `delete` コマンド

`python main.py delete <url>`

- 指定したURLのDBレコードを削除する
- 対応する `download/` 配下のファイルも削除する
- 指定したURLがDBに存在しない場合はエラーメッセージを標準エラー出力に表示して終了コード 1 で終了する

`python main.py delete --all`

- DB に登録されているすべてのレコードを削除する
- 対応する `download/` 配下のファイルもすべて削除する
- 実行前に確認プロンプト（`Delete all N entries? [y/N]: `）を表示し、`y` 以外は中断する

#### `update` コマンド

`python main.py update`

- DB に登録されているすべてのURLを再スクレイプして上書き保存する
- 再スクレイプは登録順（`scraped_at` 昇順）で逐次実行する

`python main.py update <url>`

- 指定したURLのみ再スクレイプして上書き保存する
- 指定したURLがDBに存在しない場合はエラーメッセージを標準エラー出力に表示して終了コード 1 で終了する

#### ログ

- ライブラリ: [structlog](https://www.structlog.org/)（`pip install structlog`）
- 出力先: `var/logs/app.log`（プロジェクトルート直下、ディレクトリ未存在時は自動作成）
- フォーマット: JSON（1イベント1行）
- ログローテーション: 1ファイル最大 10MB、最大 5世代保持
- タイムスタンプ: UTC ISO 8601形式

全ログエントリに共通で含むフィールド:

| フィールド  | 内容                                              |
|-------------|---------------------------------------------------|
| `timestamp` | UTC ISO 8601形式（例: `2026-04-29T10:00:00.123Z`）|
| `level`     | ログレベル（`info` / `warning` / `error`）        |
| `event`     | イベント名（下表参照）                            |
| `command`   | 実行されたコマンド名（`scrape` / `list` / `update` / `delete`）|

出力するイベントとレベル:

| event                           | レベル  | 追加フィールド                                |
|---------------------------------|---------|-----------------------------------------------|
| `command_start`                 | INFO    | `command`, `args`（コマンドライン引数）        |
| `command_end`                   | INFO    | `command`, `elapsed_sec`, `exit_code`         |
| `scrape_start`                  | INFO    | `url`                                         |
| `scrape_success`                | INFO    | `url`, `elapsed_sec`                          |
| `merge_saved`                   | INFO    | `url`, `file_path`, `pages`                   |
| `scrape_empty`                  | WARNING | `url`                                         |
| `scrape_failed`                 | ERROR   | `url`, `error`                                |
| `db_insert`                     | INFO    | `url`, `file_path`                            |
| `db_upsert`                     | INFO    | `url`, `file_path`                            |
| `db_delete`                     | INFO    | `url`, `file_path`                            |
| `db_delete_all`                 | INFO    | `count`（削除件数）                           |
| `list_output`                   | INFO    | `count`（出力件数）                           |
| `delete_all_cancelled`          | INFO    | —                                             |
| `url_not_found`                 | ERROR   | `url`                                         |
| `invalid_args`                  | ERROR   | `args`                                        |

ログ出力例:

```json
{"timestamp": "2026-04-29T10:00:00.123Z", "level": "info", "event": "command_start", "command": "scrape", "args": ["https://code.claude.com/docs/en/"]}
{"timestamp": "2026-04-29T10:00:00.124Z", "level": "info", "event": "scrape_start", "command": "scrape", "url": "https://code.claude.com/docs/en/"}
{"timestamp": "2026-04-29T10:00:02.456Z", "level": "info", "event": "scrape_success", "command": "scrape", "url": "https://code.claude.com/docs/en/quickstart", "elapsed_sec": 2.332}
{"timestamp": "2026-04-29T10:00:02.900Z", "level": "info", "event": "merge_saved", "command": "scrape", "url": "https://code.claude.com/docs/en/", "file_path": "code.claude.com_docs_en.md", "pages": 12}
{"timestamp": "2026-04-29T10:00:02.910Z", "level": "info", "event": "db_insert", "command": "scrape", "url": "https://code.claude.com/docs/en/", "file_path": "code.claude.com_docs_en.md"}
{"timestamp": "2026-04-29T10:00:02.911Z", "level": "info", "event": "command_end", "command": "scrape", "elapsed_sec": 2.337, "exit_code": 0}
```

### エラーハンドリング

| 状況                           | 挙動                                                                 |
|--------------------------------|----------------------------------------------------------------------|
| URLへのアクセス失敗            | 標準エラー出力にエラーメッセージを表示し、終了コード 1 で終了       |
| スクレイプ結果が空             | 標準エラー出力にエラーメッセージを表示し、ファイル・DB 更新は行わない|
| `download` ディレクトリ未存在 | 自動で作成する                                                       |
| `update <url>` でURL未登録    | 標準エラー出力にエラーメッセージを表示し、終了コード 1 で終了       |
| `delete <url>` でURL未登録    | 標準エラー出力にエラーメッセージを表示し、終了コード 1 で終了       |
| 引数が不正                     | 使用方法を標準エラー出力に表示し、終了コード 1 で終了               |
