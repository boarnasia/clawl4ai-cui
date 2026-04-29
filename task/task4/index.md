# task4: スクレイプ結果を1ファイルに統合（llms.txt スタイル）

## 背景・目的

現状の `python main.py <url>` は BFS でサブページを全取得し、**ページごとに個別ファイルを保存**する（task1 の仕様）。
本タスクではこれを変更し、**1コマンドで1ファイル**（AI に渡す `llms.txt` 風のマージ済みドキュメント）を出力するようにする。

task3 で追加した `merger.py` のロジック（共通ヘッダ/フッタ抽出、ボイラープレート検出）を、`merge` サブコマンド経由ではなく **scrape の通常フローに組み込む**。

## 変更後の動作

```
python main.py https://code.claude.com/docs/en/
  → download/code.claude.com_docs_en.md   ← 1ファイルのみ
```

- 個別ページファイルは **作らない**
- DB には **起点 URL を1レコード** だけ記録する（マージ済みファイルへのマッピング）
- ファイル構造（マージ済み）:

```
{サイト共通ヘッダ（1回）}

---

<!-- source: https://code.claude.com/docs/en/ -->

# Claude Code overview
...

---

<!-- source: https://code.claude.com/docs/en/quickstart -->

# Quickstart
...

---

{サイト共通フッタ（1回）}
```

## task1 仕様との差分（task1/index.md も併せて更新）

| 項目 | task1（旧） | task4（新） |
|------|-------------|-------------|
| 出力 | ページごとに1ファイル | サイトごとに1ファイル（マージ済み） |
| ファイル名 | `{url}--{title}.md` | `{url}.md`（タイトル部なし） |
| DB レコード | BFS で取得した全ページ分 | 起点 URL 1件のみ |
| `scrape_success` ログ | `url`, `file_path`, `elapsed_sec` | `url`, `elapsed_sec`（個別ページに `file_path` なし） |
| 新規イベント | — | `merge_saved`（`file_path`, `pages`） |
| `merge` コマンド | task3 で追加 | 削除（通常フローに統合） |

→ 本タスクの実装と同時に **`task/task1/index.md` の該当箇所を更新する** こと（出力仕様、ログイベント表）。

## 既存 DB の扱い

旧仕様で作成された個別ページレコードが DB に残っていると `list` 出力が混乱する。
**task4 適用前に `python main.py delete --all` を実行する運用を必須化する**（自動マイグレーションは行わない）。
README にも一行注記する。

---

## 変更対象ファイル

| ファイル | 変更種別 |
|----------|----------|
| `scraper.py` | 修正（BFS 結果を返すだけにし、保存処理を削除） |
| `merger.py` | 修正（`Path` 引数を文字列引数に変更） |
| `main.py` | 修正（`cmd_scrape` でマージ＆保存、`cmd_update` を再構成、`cmd_merge` 削除） |
| `task/task1/index.md` | 仕様差分の反映 |
| `README.md` | 使用例の更新、移行注記 |

その他のファイルは変更対象外。

---

## 実装ステップ

### Step 1: `scraper.py`

**目的:** BFS の結果を「メモリ上で `(url, markdown)` のリストとして返す」だけにする。ファイル保存責務を呼び出し側に移す。

差分の要点:

- `build_filename(url, title)` を削除し、`build_merged_filename(url) -> str` を追加
  - 例: `https://code.claude.com/docs/en/` → `code.claude.com_docs_en.md`
  - 既存の `_sanitize` をそのまま流用
- `scrape()` の戻り値を `list[tuple[str, str]]` に変更（`str` = filename → `str` = markdown 本文）
- `scrape()` 内の `Path("download").mkdir(...)` と `Path(...).write_text(...)` を削除
- `scrape_success` ログから `file_path` フィールドを削除
- `scrape_single()` を **関数ごと削除**（後述の `cmd_update` で使わなくなるため）

完成イメージ（要所のみ）:

```python
def build_merged_filename(url: str) -> str:
    bare = re.sub(r"^https?://", "", url).rstrip("/")
    return _sanitize(bare) + ".md"


async def scrape(url, command, log) -> list[tuple[str, str]] | bool:
    """Returns list of (page_url, markdown_text), or False on failure."""
    # ... BFS は現状のまま ...
    pages = []
    for result in results:
        if not result.success:
            continue
        markdown = getattr(result.markdown, "raw_markdown", None) or str(result.markdown or "")
        if not markdown.strip():
            continue
        log.info("scrape_success", command=command, url=result.url,
                 elapsed_sec=round(time.monotonic() - start, 3))
        pages.append((result.url, markdown))

    if not pages:
        log.warning("scrape_empty", command=command, url=url)
        return False

    log.info("scrape_complete", command=command, start_url=url,
             pages=len(pages), elapsed_sec=round(time.monotonic() - start, 3))
    return pages
```

### Step 2: `merger.py`

**目的:** ファイル読み込み責務を呼び出し側に寄せ、純粋にメモリ上のテキストを操作する関数にする。

差分の要点:

- `from pathlib import Path` を削除
- `merge(entries: list[tuple[str, Path]], ...)` → `merge(pages: list[tuple[str, str]], ...)` に変更
- 関数冒頭の `loaded = [(url, p.read_text(...)) for ...]` を削除し、引数 `pages` をそのまま使う
- 内部で `loaded` を参照していた箇所を `pages` に置換
- `_build_boilerplate` と `_split` のロジックは **変更なし**（task3 で確立済みのため）

### Step 3: `main.py`

**`cmd_scrape` を書き換え:**

```python
async def cmd_scrape(url: str, command: str, log) -> None:
    pages = await scraper.scrape(url, command, log)
    if pages is False:
        _exit_error(f"failed to scrape {url}")

    merged = merger.merge(pages)
    filename = scraper.build_merged_filename(url)
    Path("download").mkdir(exist_ok=True)
    Path(f"download/{filename}").write_text(merged, encoding="utf-8")
    log.info("merge_saved", command=command, file_path=filename, pages=len(pages))

    action = db.upsert(url, filename)
    event = "db_insert" if action == "inserted" else "db_upsert"
    log.info(event, command=command, url=url, file_path=filename)
```

**`cmd_update` を書き換え（重要: 全件 update 時に1件失敗しても継続する挙動を維持する）:**

旧コードは `scrape_single` の失敗を `continue` でスキップしていた。`cmd_scrape` をそのまま呼ぶと `_exit_error` で全体が止まるため、**`cmd_scrape` を呼ばずに同等処理を inline 展開**し、全件ループ時のみ try/continue する。

```python
async def _scrape_one(url: str, command: str, log) -> bool:
    """Single-URL scrape+merge+save. Returns True on success, False on failure."""
    pages = await scraper.scrape(url, command, log)
    if pages is False:
        return False
    merged = merger.merge(pages)
    filename = scraper.build_merged_filename(url)
    Path("download").mkdir(exist_ok=True)
    Path(f"download/{filename}").write_text(merged, encoding="utf-8")
    log.info("merge_saved", command=command, file_path=filename, pages=len(pages))
    action = db.upsert(url, filename)
    event = "db_insert" if action == "inserted" else "db_upsert"
    log.info(event, command=command, url=url, file_path=filename)
    return True


async def cmd_scrape(url: str, command: str, log) -> None:
    if not await _scrape_one(url, command, log):
        _exit_error(f"failed to scrape {url}")


async def cmd_update(args: list[str], log) -> None:
    url = args[1] if len(args) > 1 else None
    if url:
        if not db.get_by_url(url):
            log.error("url_not_found", command="update", url=url)
            _exit_error(f"URL not found in DB: {url}")
        if not await _scrape_one(url, "update", log):
            _exit_error(f"failed to scrape {url}")
    else:
        rows = db.list_all()
        for _, u, _ in rows:
            await _scrape_one(u, "update", log)  # 失敗しても次へ
```

**`cmd_merge` を関数ごと削除し、`main()` 内のルーティング `elif cmd == "merge":` も削除。USAGE 文字列から `merge` 行を削除。**

### Step 4: ドキュメント更新

- `task/task1/index.md`: 上記「task1 仕様との差分」表に従い、出力仕様・ログイベント表を更新
- `README.md`: `merge` コマンドの記述を削除、「旧仕様の DB レコードが残っている場合は `delete --all` を実行」の注記を追加

---

## 検証手順

```bash
# 1. クリーン状態にする
echo "y" | uv run python main.py delete --all 2>/dev/null || true
find download -name '*.md' -type f -delete

# 2. サブページが複数ある実サイトでスクレイプ
uv run python main.py https://code.claude.com/docs/en/

# 3. download/ にマージ済み1ファイルのみ
ls download/
# 期待: code.claude.com_docs_en.md のみ

# 4. マージ構造の確認（共通ヘッダ・複数 source・共通フッタ）
grep -c "<!-- source:" download/code.claude.com_docs_en.md
# 期待: 2 以上（複数ページがマージされている）

head -20 download/code.claude.com_docs_en.md
# 期待: ヘッダ → "---" → "<!-- source: ... -->" の流れ

# 5. DB は起点 URL の1レコードのみ
uv run python main.py list
# 期待: https://code.claude.com/docs/en/  code.claude.com_docs_en.md  の1行

# 6. update <url> が動作（再 BFS → 上書き）
uv run python main.py update https://code.claude.com/docs/en/
ls -la download/  # 同ファイルの mtime が更新されていること

# 7. update（全件）で1件失敗しても継続することの確認
#    → 存在しないURLを直接DBに混ぜてから全件 update を実行
uv run python -c "import db; db.init_db(); db.upsert('https://invalid.example.invalid/', 'invalid.md')"
uv run python main.py update
# 期待: invalid.example.invalid は scrape_failed ログ→continue、
#       他のURL（code.claude.com/docs/en/）は成功する
uv run python main.py delete https://invalid.example.invalid/  # 後始末

# 8. delete が動作
uv run python main.py delete https://code.claude.com/docs/en/
ls download/         # 空
uv run python main.py list  # 空

# 9. merge コマンドが廃止されていること
uv run python main.py merge 2>&1 | head -5
# 期待: USAGE が表示され exit 1

# 10. インポートエラーがないこと
uv run python -c "import main; import scraper; import merger; print('OK')"
```

## 受け入れ基準

- 検証手順 1〜10 が全て期待どおり動作する
- `task/task1/index.md` のログイベント表に `merge_saved` が追加され、`scrape_success` から `file_path` が外れている
- `task/task1/index.md` の「ページごとに1ファイル」記述が「サイトごとに1マージ済みファイル」に更新されている
- `README.md` から `merge` コマンドの記述が消え、移行注記が追加されている
- `scraper.scrape_single()`、`scraper.build_filename()`、`main.cmd_merge()` がコードベースから消えている
