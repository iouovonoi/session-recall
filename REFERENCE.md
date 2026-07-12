# Session Recall 完整參考 / Full Reference

這份文件提供進階使用、輸出欄位、內部設計與排錯說明。安裝與日常使用請先看 [README.md](README.md)。

This file covers advanced usage, output fields, internals, and troubleshooting. For installation and daily use, start with [README.md](README.md).

## 安裝細節 / Install Details

第一次使用前，agent 應該先說明它會讀取哪些本機資料，並取得你的同意。`install.ps1` 只會建立本機索引與必要資料夾。

Before first use, the agent should explain what local data it will read and get your consent. `install.ps1` only creates the local index and required folders.

| 會做 / It will | 不會做 / It will not |
|---|---|
| 建立 `~\SessionRecall` 與 SQLite 索引 / Create `~\SessionRecall` and a SQLite index | 讀取別人的資料 / Touch anyone else's data |
| 從你的 `~\.copilot\session-store.db` 匯入最近 session / Import recent sessions from your own `~\.copilot\session-store.db` | 上傳資料 / Upload data |
| 只有指定 `-InstallScheduler` 時才安裝排程 / Install a schedule only with `-InstallScheduler` | 未經同意安裝背景排程 / Install a schedule without consent |

## 可以分享什麼？/ Sharing This Skill

| 可以分享 / Share | 不要分享 / Never share |
|---|---|
| `SKILL.md`, `README.md`, `REFERENCE.md`, `docs\`, `install.ps1`, `scripts\*` | `~\SessionRecall\` |
| 原始碼與文件 / Source and documentation | `~\.copilot\session-store.db` |
| | `~\.copilot\session-state\` or other memory stores |

## 腳本 / Scripts

| 檔案 / File | 用途 / Purpose |
|---|---|
| `scripts/memory_tool.py` | 核心工具：SQLite/FTS 索引、搜尋、compare、report、graph、context pack / Core tool for SQLite/FTS indexing, search, compare, report, graph, and context packs |
| `scripts/session-recall.ps1` | Windows wrapper，設定 UTF-8 並呼叫 Python / Windows wrapper that sets UTF-8 and calls Python |
| `install.ps1` | 初始化索引、可選匯入 session、可選安裝排程 / Initializes the index, optionally imports sessions, optionally installs the schedule |
| `scripts/install-session-recall-scheduler.ps1` | 安裝 Windows Task Scheduler 工作 / Installs the Windows Task Scheduler job |

## 常用指令 / Commands at a Glance

| 指令 / Command | 用途 / What it does |
|---|---|
| `init` | 建立本機索引 / Create the local index |
| `sync-copilot --limit N` | 從 Copilot session store 匯入 N 筆 session / Import N sessions from the Copilot session store |
| `sync-copilot --compare "query"` | 匯入後比較目前 query 與過去 session / Import and compare the query against past sessions |
| `sync-copilot --compare "query" --report` | 產生 context 節省量報告 / Generate a context-savings report |
| `search "query"` | 搜尋本機索引 / Search the local index |
| `context-pack "query"` | 匯出相關 session 的 Markdown context pack / Export a Markdown context pack |
| `graph` | 輸出 session/topic/entity 關聯圖 JSON / Output a session/topic/entity graph JSON |
| `benchmark testset.jsonl` | 用 JSONL 測試集跑本機 benchmark / Run a local benchmark from a JSONL test set |
| `log-event` | 手動記錄事件，供之後 compact / Manually log events for later compaction |

範例：

Example:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.copilot\skills\session-recall\scripts\session-recall.ps1" sync-copilot --limit 50 --compare "session recall validation" --compare-limit 5
```

## `compare` 輸出欄位 / `compare` Result Fields

| 欄位 / Field | 意義 / Meaning | 使用建議 / How to use it |
|---|---|---|
| `context_used` | 是否找到高信心匹配 / Whether a high-confidence match was found | `true` 時才建議注入 context / Inject context only when true |
| `confidence` | 最高匹配分數 / Highest match score | 用於粗略排序，不是精準機率 / Useful for rough ranking, not an exact probability |
| `matched_sessions` | 高信心 session / High-confidence sessions | 可作為 agent context / Good candidates for agent context |
| `candidate_sessions` | 低信心候選 / Lower-confidence candidates | 可檢查但不建議自動注入 / Inspectable, but avoid automatic injection |
| `fallback_sessions` | 無匹配時的最近 session / Recent sessions when there is no match | 只作參考 / Reference only |
| `diagnostics` | token、FTS、fallback 等診斷資訊 / Token, FTS, and fallback diagnostics | 排錯用 / For troubleshooting |
| `quality_flags` | 例如 `automation_like_session` / Flags such as `automation_like_session` | 代表可能要降低信任 / Indicates lower trust |

## `report` 輸出欄位 / `report` Result Fields

`--report` 需要搭配 `--compare`。它會估算 raw context 與 recommended context 的大小差異。

`--report` requires `--compare`. It estimates the size difference between raw context and recommended context.

| 欄位 / Field | 意義 / Meaning |
|---|---|
| `recommended_context` | 建議注入的精簡 metadata，不含完整 raw turns / Trimmed metadata recommended for injection, without full raw turns |
| `recommended_context_truncated` | 是否因 `--max-context-chars` 被截斷 / Whether it was trimmed by `--max-context-chars` |
| `metrics.raw_context_chars` / `estimated_raw_tokens` | 原始內容大小與粗略 token 估算 / Raw content size and rough token estimate |
| `metrics.recommended_context_chars` / `estimated_recommended_tokens` | 建議內容大小與粗略 token 估算 / Recommended context size and rough token estimate |
| `metrics.estimated_tokens_saved` / `estimated_savings_percent` | 估計節省量；無匹配時為 0 / Estimated savings; 0 when there is no match |

token 估算只是 `ceil(chars / 4)`，不是精準 tokenizer。

The token estimate is only `ceil(chars / 4)`. It is not an exact tokenizer.

## Session JSON 格式 / Session JSON Shape

```json
{
  "session_id": "20260611-memory-platform-planning",
  "title": "規劃 Copilot Memory",
  "essence": "討論如何建立本機優先的 session recall 與 context pack 流程",
  "summary": "整理 memory 索引、搜尋、graph 與 report 的設計方向。",
  "topics": ["memory", "local-first", "semantic-search", "session-search"],
  "entities": ["SQLite FTS5", "Markdown", "JSONL", "Copilot"],
  "decisions": ["使用本機 SQLite FTS5 作為第一版索引"],
  "open_questions": ["是否需要 team-shared memory"],
  "content": "conversation notes",
  "importance": 5
}
```

## 輸出資料夾 / Output Folders

| 路徑 / Path | 內容 / Contents |
|---|---|
| `~\SessionRecall\memory.sqlite` | SQLite + FTS5 索引 / SQLite + FTS5 index |
| `~\SessionRecall\raw-events\*.jsonl` | raw event log |
| `~\SessionRecall\sessions\*.md` | 可閱讀的 session 摘要 / Human-readable session summaries |
| `~\SessionRecall\sessions\*.summary.json` | session metadata |
| `~\SessionRecall\exports\context-pack-*.md` | 匯出的 context pack / Exported context packs |
| `~\SessionRecall\graph\memory-graph.json` | session/topic/entity graph |

## 簡短原理 / How It Works

- 從 Copilot CLI 的 `~\.copilot\session-store.db` 讀取 session 與 turns。
- It reads sessions and turns from Copilot CLI's `~\.copilot\session-store.db`.
- `sync-copilot` 將內容整理成 Markdown、JSON 與 SQLite FTS5 索引。
- `sync-copilot` turns the content into Markdown, JSON, and a SQLite FTS5 index.
- `compare` 使用 FTS 與 token overlap 找出相關 session，並只回傳高信心項目作為 `matched_sessions`。
- `compare` uses FTS and token overlap to find related sessions, returning only high-confidence items as `matched_sessions`.
- `report` 估算 raw context 與 recommended context 的大小差異。
- `report` estimates the size difference between raw context and recommended context.

## FAQ

| 問題 / Question | 回答 / Answer |
|---|---|
| Copilot CLI 沒有載入 skill？ / Copilot CLI did not load the skill? | 確認路徑是 `~\.copilot\skills\session-recall\SKILL.md`，然後重啟 Copilot CLI / Check the path and restart Copilot CLI |
| 沒有建立索引？ / No index was created? | 執行 `install.ps1` 或 `session-recall.ps1 init` / Run `install.ps1` or `session-recall.ps1 init` |
| `--report` 報錯？ / `--report` errors? | `--report` 必須搭配 `--compare` / `--report` must be used with `--compare` |
| 找不到 Python？ / Python cannot be found? | 安裝 Python 3，或設定 `SESSION_RECALL_PYTHON` 指向 `python.exe` / Install Python 3 or set `SESSION_RECALL_PYTHON` to `python.exe` |
| 可以分享本機索引嗎？ / Can I share the local index? | 不建議，索引可能含有私人對話 / No, it may contain private conversation data |
