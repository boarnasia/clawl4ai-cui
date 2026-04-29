# crawl4ai-cui

Web ページを Markdown 形式でスクレイプして保存する CLI ツールです。  
指定 URL 配下を再帰的に全取得し、スクレイプ履歴を SQLite で管理します。  
AI への入力として使いやすいよう、起点URLごとに1つの統合Markdownとして出力します。

## 必要環境

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

## セットアップ

```bash
git clone https://github.com/boarnasia/clawl4ai-cui
cd clawl4ai-cui
uv sync
```

## 使い方

### URL をスクレイプして保存

```bash
uv run python main.py https://code.claude.com/docs/en/
```

指定 URL を起点に、**同一 URL プレフィックス配下のページを再帰的（BFS）に全取得**します。  
外部ドメインへのリンクは辿りません。

取得したページは `download/` ディレクトリに **起点URLごとに1ファイル** で保存されます。

**保存ファイル名の規則:** `<URLパート>.md`

| URL | ファイル名 |
|-----|-----------|
| `https://code.claude.com/docs/en/` | `code.claude.com_docs_en.md` |
| `https://example.com/` | `example.com.md` |

重複するヘッダ・フッタ（ナビゲーション等）は自動検出して1回だけ出力し、各ページのボディを連結します。

```
{サイト共通ヘッダ（1回のみ）}

---

<!-- source: https://code.claude.com/docs/en/ -->

# Claude Code overview
...

---

<!-- source: https://code.claude.com/docs/en/quickstart -->

# Quickstart
...

---

{サイト共通フッタ（1回のみ）}
```

### スクレイプ済み一覧を表示

```bash
uv run python main.py list
```

```
2026-04-29T10:00:00+00:00	https://example.com/	example.com.md
```

タブ区切りで `scraped_at / url / file_path` を出力します。`grep` でフィルタできます。

```bash
uv run python main.py list | grep docs/en
```

### ドキュメントを更新

```bash
# すべて再スクレイプ（起点URLごと）
uv run python main.py update

# 特定 URL だけ再スクレイプ
uv run python main.py update https://example.com/
```

### エントリを削除

```bash
# 特定 URL のファイルと履歴を削除
uv run python main.py delete https://example.com/

# すべて削除（確認プロンプトあり）
uv run python main.py delete --all
```

旧仕様（ページごとに個別ファイル保存）で作成したDBレコードが残っている場合、task4適用前に次を実行してください。

```bash
uv run python main.py delete --all
```

## ファイル構成

```
.
├── main.py          # エントリポイント・コマンドルーティング
├── scraper.py       # スクレイプ処理・ファイル名変換（BFS再帰取得）
├── merger.py        # 複数ページの Markdown 結合
├── db.py            # SQLite 操作
├── logger.py        # ログ設定（structlog）
├── sqlite.db        # スクレイプ履歴（自動生成）
├── download/        # 起点URLごとの統合 Markdown ファイル
└── var/logs/
    └── app.log      # 操作ログ（JSON 形式）
```

## ログ

すべての操作は `var/logs/app.log` に JSON 形式で記録されます。

```json
{"command": "scrape", "url": "https://example.com/", "event": "command_start", "timestamp": "2026-04-29T10:00:00.000Z", "level": "info"}
{"command": "scrape", "url": "https://example.com/docs/start", "elapsed_sec": 1.5, "event": "scrape_success", "timestamp": "2026-04-29T10:00:01.500Z", "level": "info"}
{"command": "scrape", "url": "https://example.com/", "file_path": "example.com.md", "pages": 7, "event": "merge_saved", "timestamp": "2026-04-29T10:00:01.900Z", "level": "info"}
{"command": "scrape", "start_url": "https://example.com/", "pages": 42, "elapsed_sec": 38.2, "event": "scrape_complete", "timestamp": "2026-04-29T10:00:38.200Z", "level": "info"}
```

`jq` でフィルタできます。

```bash
# エラーだけ確認
cat var/logs/app.log | jq 'select(.level == "error")'

# 特定 URL の操作履歴
cat var/logs/app.log | jq 'select(.url == "https://example.com/")'
```
