---
name: session-recall
description: Synchronize Copilot CLI native sessions into a local session recall index, then search, compare, export context packs, and generate memory graphs. Use for every text conversation, session recall, previous context, similar sessions, context pack, or memory graph.
allowed-tools: "Read(**) Bash(*) Shell(*) Shell(pwsh:*) powershell"
---

# Session Recall

Session Recall 會把 Copilot CLI 的本機 session store 同步到 `~\SessionRecall`，建立可搜尋的本機索引。它適合用來找回過去相似對話、產生 context pack、或輸出 memory graph。

Session Recall synchronizes Copilot CLI's local session store into `~\SessionRecall` and builds a searchable local index. Use it to recall similar past conversations, generate context packs, or output a memory graph.

## 觸發時機 / Trigger

當使用者提到以下任一情境時使用本 skill：

Use this skill when the user mentions any of these needs:

- session recall、previous context、similar sessions、search memory
- 回想先前對話、查找過去 session、尋找相關上下文
- sync Copilot session、context pack、memory graph
- 同步 Copilot session、匯出 context pack、建立記憶關聯圖

## 主要指令 / Main Command

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.copilot\skills\session-recall\scripts\session-recall.ps1" sync-copilot --limit 50 --compare "<current message>" --compare-limit 5
```

## 如何使用結果 / How to Use the Result

優先看這三個欄位：

Start with these three fields:

| 欄位 / Field | 意義 / Meaning |
|---|---|
| `compare.context_used` | 是否找到高信心匹配 / Whether a high-confidence match was found |
| `compare.matched_sessions` | 可注入的相關 session / Relevant sessions suitable for context |
| `compare.candidate_sessions` | 低信心候選，只作參考 / Lower-confidence candidates for reference only |

如果 `context_used=true`，可以摘要 `matched_sessions` 中最相關的 1 到 2 筆資訊作為回覆上下文。

If `context_used=true`, summarize the top 1-2 items from `matched_sessions` as context for the response.

如果 `context_used=false`，不要假裝找到記憶；可簡短說明目前沒有高信心相關 session。

If `context_used=false`, do not pretend memory was found. Briefly state that no high-confidence related session was available.

## 安裝 / Install

如果索引不存在，先請使用者同意，然後執行：

If the index does not exist, ask for user consent first, then run:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.copilot\skills\session-recall\install.ps1"
```

## 隱私規則 / Privacy Rules

- 只讀取使用者自己的 `~\.copilot\session-store.db`。
- Read only the user's own `~\.copilot\session-store.db`.
- 預設輸出都在 `~\SessionRecall`。
- Generated data is stored under `~\SessionRecall` by default.
- 不要分享 `~\SessionRecall`、`~\.copilot\session-store.db`、`~\.copilot\session-state` 或其他 memory store。
- Do not share `~\SessionRecall`, `~\.copilot\session-store.db`, `~\.copilot\session-state`, or other memory stores.

## 更多文件 / More Documentation

| 文件 / File | 用途 / Purpose |
|---|---|
| `README.md` | 安裝與日常使用 / Install and daily use |
| `REFERENCE.md` | 完整欄位、FAQ、內部設計 / Full fields, FAQ, internals |
| `docs/validation.md` | report 與 benchmark 說明 / Report and benchmark explanation |
