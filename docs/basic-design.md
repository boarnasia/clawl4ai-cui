# 基本設計

## 概要

crawl4ai を使って Web ページを Markdown 形式でスクレイプし、ローカルに保存するCLIツール。スクレイプ履歴をSQLiteで管理し、再取得・削除・一覧操作をサポートする。

---

## ディレクトリ構成

```
.
├── main.py              # エントリポイント
├── sqlite.db            # スクレイプ履歴DB（初回実行時に自動生成）
├── download/            # スクレイプ結果Markdownファイルの保存先
├── var/
│   └── logs/
│       └── app.log      # 操作ログ（structlog、JSON形式）
├── docs/
│   └── basic-design.md  # 本ドキュメント
└── pyproject.toml
```

---

## コマンド一覧

| コマンド                      | 説明                                       |
|-------------------------------|--------------------------------------------|
| `python main.py <url>`        | 指定URLをスクレイプして保存                |
| `python main.py list`         | スクレイプ済みURLを一覧出力                |
| `python main.py update`       | 全URLを再スクレイプ                        |
| `python main.py update <url>` | 指定URLを再スクレイプ                      |
| `python main.py delete <url>` | 指定URLのレコードとファイルを削除          |
| `python main.py delete --all` | 全レコードとファイルを削除（確認あり）     |

---

## データ設計

### `sqlite.db` — テーブル: `scrape_history`

| カラム名   | 型      | 制約                  | 説明                                           |
|------------|---------|-----------------------|------------------------------------------------|
| id         | INTEGER | PRIMARY KEY AUTOINCREMENT | —                                          |
| url        | TEXT    | UNIQUE NOT NULL       | スクレイプしたURL                              |
| file_path  | TEXT    | NOT NULL              | `download/` からの相対パス                     |
| scraped_at | TEXT    | NOT NULL              | 最終スクレイプ日時（UTC ISO 8601）             |

同一URLを再スクレイプした場合は `url` キーで UPSERT（`file_path`・`scraped_at` を更新）。

### `download/` — ファイル命名規則

`<urlパート>--<ページタイトル>.md`

- プロトコル（`https://` 等）は除去
- 末尾スラッシュは除去
- `/` → `_`、スペース → `_`、パスに使えない文字（`? # & = * " < > | \ :`）→ `_`
- urlパートとページタイトルは `--` で区切る

---

## ログ設計

### 設定

| 項目           | 値                              |
|----------------|---------------------------------|
| ライブラリ     | structlog                       |
| 出力先         | `var/logs/app.log`              |
| フォーマット   | JSON（1イベント1行）            |
| ローテーション | 10MB × 5世代                    |
| タイムスタンプ | UTC ISO 8601                    |

### 共通フィールド

全ログエントリに `timestamp` / `level` / `event` / `command` を含む。

### イベント一覧

| event                  | level   | 発生タイミング                         |
|------------------------|---------|----------------------------------------|
| `command_start`        | info    | コマンド処理の開始時                   |
| `command_end`          | info    | コマンド処理の正常終了時               |
| `scrape_start`         | info    | URL取得開始時                          |
| `scrape_success`       | info    | URL取得・ファイル保存完了時            |
| `scrape_empty`         | warning | 取得結果が空だった場合                 |
| `scrape_failed`        | error   | URL取得に失敗した場合                  |
| `db_insert`            | info    | DBへの新規登録完了時                   |
| `db_upsert`            | info    | DBの既存レコード更新完了時             |
| `db_delete`            | info    | DBレコード削除完了時                   |
| `db_delete_all`        | info    | 全レコード削除完了時                   |
| `list_output`          | info    | `list` コマンド出力完了時              |
| `delete_all_cancelled` | info    | `delete --all` を確認プロンプトで中断  |
| `url_not_found`        | error   | 指定URLがDBに存在しない場合            |
| `invalid_args`         | error   | 引数が不正な場合                       |

---

## 依存ライブラリ

| ライブラリ  | 用途                          |
|-------------|-------------------------------|
| crawl4ai    | Webスクレイプ・Markdown変換   |
| structlog   | 構造化ログ出力                |

---

## エラーハンドリング方針

- 異常終了時は標準エラー出力にメッセージを表示し、終了コード `1` で終了
- `download/`・`var/logs/` ディレクトリは起動時に存在しなければ自動作成
- スクレイプ結果が空の場合はファイル・DB を更新しない
