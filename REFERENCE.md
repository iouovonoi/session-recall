# Session Recall — 完整參考文件 / Full Reference

> 一般安裝與日常使用請先看 `README.md`。這份文件是給想深入了解細節、或需要排查問題的人看的。
> For install & daily use, read `README.md` first. This file is for deeper detail and troubleshooting only.

## 安裝細節 / Install details

第一次使用時，agent 要先說明會做什麼、取得同意才能執行。`install.ps1` 只會做以下事情：

On first use, the agent must explain what it will do and get consent before running. `install.ps1` only does this:

| 會做 It will | 不會做 It won't |
|---|---|
| 建立 `~/SessionRecall` 資料夾與 SQLite 索引 Create `~/SessionRecall` + SQLite index | 讀取或複製別人的資料 Touch anyone else's data |
| 從你自己的 `~\.copilot\session-store.db` 匯入最多 200 筆 session Import up to 200 of your own sessions | 上傳任何資料 Upload anything |
| 安裝排程（僅在加 `-InstallScheduler` 時） Install a schedule (only with `-InstallScheduler`) | 未經同意安裝排程 Install a schedule without consent |

參數：`-InitialSyncLimit 500`（改匯入數量）、`-SkipInitialSync`（只建空索引）、`-InstallScheduler -EveryMinutes 30`（自動同步）。

## 分享這個 skill 給別人 / Sharing this skill

| 可以分享 Share | 不要分享 Never share |
|---|---|
| `SKILL.md` / `README.md` / `REFERENCE.md` / `docs\` / `install.ps1` / `scripts\*` | `~\SessionRecall\`、`~\CopilotMemory\` |
| | `~\.copilot\session-store.db`、`~\.copilot\session-state\` |
| | `~\.copilot-buddy\memory\` |

安裝方式：把整個 `session-recall` 資料夾放到 `%USERPROFILE%\.copilot\skills\session-recall`，重開 Copilot CLI，第一次觸發時同意執行 `install.ps1`。

## 主要腳本 / Scripts

| 檔案 | 用途 |
|---|---|
| `memory_tool.py` | 實際邏輯：SQLite/FTS 索引、搜尋、graph、context pack、report、benchmark |
| `session-recall.ps1` | Windows 包裝腳本，固定 UTF-8 輸出、自動找 Python |
| `install.ps1` | 初次安裝、匯入既有 session、選擇性安裝排程 |
| `install-session-recall-scheduler.ps1` | 安裝 Windows 排程工作，定期同步 |

## 指令一覽 / Commands at a glance

| 指令 Command | 做什麼 What it does |
|---|---|
| `init` | 只建立空索引 |
| `sync-copilot --limit N` | 從 Copilot 原生 session store 匯入 N 筆 session |
| `sync-copilot --compare "問題"` | 匯入後，順便比對目前問題有沒有相似的過去 session |
| `sync-copilot --compare "問題" --report` | 同上，再加一份「有沒有省 token」的量化報告，見 `docs/validation.md` |
| `search "關鍵字"` | 只做搜尋，不重新匯入 |
| `context-pack "關鍵字"` | 把相關 session 整理成一份可貼回對話的 Markdown |
| `graph` | 產生 session / topic / entity 的關聯圖 JSON |
| `benchmark testset.jsonl` | 自測工具，吃固定題庫算命中率，公開發文前用 |
| `log-event` | 備用管道：讀不到原生 DB 時，先把每一輪對話寫下來 |

範例：

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.copilot\skills\session-recall\scripts\session-recall.ps1" sync-copilot --limit 50 --compare "我想找之前談過的 session recall 設計" --compare-limit 5
```

## `compare` 回傳欄位 / `compare` result fields

| 欄位 | 意思 | 可不可以當作已參照的依據 |
|---|---|---|
| `context_used` | 有沒有找到高信心的過去 session | — |
| `confidence` | 最高命中分數 | — |
| `matched_sessions` | 高信心相關 session | ✅ 可以引用 |
| `candidate_sessions` | 低信心候選 | ❌ 只能當提示，不能宣稱已參照 |
| `fallback_sessions` | 完全沒命中時列出最近幾筆 session | ❌ 僅供人工確認 |
| `diagnostics` | 索引筆數、query tokens、命中數等除錯資訊 | — |
| `quality_flags` | 例如 `automation_like_session`＝內部技能執行紀錄，已被降權 | — |

## `report` 回傳欄位 / `report` result fields

`--report` 必須搭配 `--compare`，否則會直接回傳錯誤（非零結束碼）。

| 欄位 | 意思 |
|---|---|
| `recommended_context` | 建議注入的精簡內容（title/essence/summary/topics/matched_terms/reason），不含完整對話原文 |
| `recommended_context_truncated` | 是否因超過 `--max-context-chars`（預設 2500）而被裁減 |
| `metrics.raw_context_chars` / `estimated_raw_tokens` | 原始內容字數與估算 token 數 |
| `metrics.recommended_context_chars` / `estimated_recommended_tokens` | 建議注入內容字數與估算 token 數 |
| `metrics.estimated_tokens_saved` / `estimated_savings_percent` | 省下多少；沒命中時一律是 0，不會硬湊數字 |

實測數據與怎麼解讀，看 [`docs/validation.md`](docs/validation.md)。

## 與 session-to-memory 的分工 / vs. session-to-memory

| 這個做什麼 | 屬於哪個 skill |
|---|---|
| 搜尋、比對相似 session、context pack、graph | `session-recall`（這個） |
| 每日重點整理、決策/偏好/待辦追蹤，給人看 | `session-to-memory` |

## Session JSON 格式 / Session JSON shape

```json
{
  "session_id": "20260611-memory-platform-planning",
  "title": "本地優先 Copilot Memory 平台規劃",
  "essence": "規劃一個本地保存、可搜尋相似 session、可壓縮上下文並定期產 graph 的 memory 平台。",
  "summary": "本次討論規劃新平台的 memory 能力...",
  "topics": "memory,local-first,semantic-search,session-search,knowledge-graph",
  "entities": "SQLite FTS5,sqlite-vec,LanceDB,Markdown,JSONL,Copilot",
  "decisions": "以 local-first vault 作為核心,先落地 SQLite FTS5 與文本化儲存",
  "open_questions": "是否允許 team-shared memory,是否要內建本地 embedding 模型",
  "content": "對話重點或原始筆記。",
  "importance": 5
}
```

## 輸出資料夾 / Output folders

| 路徑 | 內容 |
|---|---|
| `~/SessionRecall/memory.sqlite` | SQLite 索引與 FTS5 |
| `~/SessionRecall/raw-events/*.jsonl` | 備用 raw event log |
| `~/SessionRecall/sessions/*.md` | 人可讀的 session 摘要 |
| `~/SessionRecall/sessions/*.summary.json` | 結構化 session 摘要 |
| `~/SessionRecall/exports/context-pack-*.md` | 可貼回對話的 context pack |
| `~/SessionRecall/graph/memory-graph.json` | session / topic / entity 關聯圖 |

## 運作原理（簡述） / How it works (short version)

- 主要資料來源是 Copilot CLI 原生 `~\.copilot\session-store.db`：`sessions` 表給 metadata，`turns` 表給對話原文。
- `sync-copilot` 把這些轉成本機 Markdown + JSON，並寫入 SQLite FTS5 全文索引。
- 搜尋時先用 FTS5 找，再用關鍵字重疊補分；中英文都支援，會過濾常見停用詞。
- 命中結果依分數、重要性、時間排序；高信心放 `matched_sessions`，低信心放 `candidate_sessions`。
- 看起來像是技能執行紀錄（例如標題含「先讀取 SKILL 文件了解規範」）會被標記 `automation_like_session` 並降權，避免蓋掉真正的人機對話。
- `log-event` / `compact-events` 是備用管道，只有讀不到原生 DB 時才用。

## 常見問題 / FAQ

| 問題 | 解法 |
|---|---|
| Copilot CLI 找不到這個 skill | 確認檔案在 `~\.copilot\skills\session-recall\SKILL.md`，重開 Copilot CLI |
| 第一次用沒有索引 | 取得同意後執行 `install.ps1`，預設匯入最多 200 筆 |
| 終端機中文顯示亂碼 | 只是 console 顯示問題，檔案本身是 UTF-8，用檔案檢視即可確認 |
| 搜尋結果太少 | 先確認已跑過 `sync-copilot`，再用短一點的關鍵字重試 |
| raw events 什麼時候變成 session | 執行 `compact-events`，或安裝排程 `install-session-recall-scheduler.ps1` |
| Graph 沒資料 | 先要有至少一筆 session，再執行 `graph` |
| 想要語意搜尋（不只是關鍵字） | 目前是 FTS5 + 關鍵字重疊，之後可以接 sqlite-vec 或 LanceDB |
| 想要自動攔截每次對話 | 需要平台提供 hook；目前靠 SKILL.md 的觸發詞讓 agent 主動呼叫 |
| `--report` 一直報錯 | 確認同時有加 `--compare`，`--report` 不能單獨使用 |
| 找不到 Python | 安裝 Python 3，或設定環境變數 `SESSION_RECALL_PYTHON` 指向你的 `python.exe` |
