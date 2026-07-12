---
name: session-recall
description: Synchronize Copilot CLI native sessions into a local session recall index, then search, compare, export context packs, and generate memory graphs. Use for every text conversation, session recall, previous context, similar sessions, context pack, or memory graph.
allowed-tools:
    - Read(**)
    - Bash(*)
    - Shell(*)
    - Shell(pwsh:*)
    - powershell
---

# Session Recall

把 Copilot CLI 原生 `session-store.db` 當作唯一資料來源，同步成本機可搜尋的 session 摘要索引，
用來判斷目前對話有沒有相似的過去 session。這是 **retrieval 工具**，不是每日人工整理 memory 的工具。
資料只存在使用者本機 `~/SessionRecall`，不上傳雲端。

> 完整安裝細節、指令列表、FAQ、JSON 格式，都在 `REFERENCE.md`；一般使用者可先看 `README.md`。
> 只有 troubleshoot、首次安裝、或使用者明確要細節時才用 view 工具查閱，不要整段塞進 context。

## 觸發詞

中文：任何文字對話、每次對話、session recall、查之前對話、找相似session、同步copilot session、搜尋memory、匯出context、產生memory graph。
English：any message、every turn、session recall、previous context、similar sessions、sync copilot session、search memory、context pack、memory graph。

## 每次觸發要做的事

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.copilot\skills\session-recall\scripts\session-recall.ps1" sync-copilot --limit 50 --compare "<current message>" --compare-limit 5
```

只需要看回傳的這 3 個欄位：

| 欄位 | 意思 |
|---|---|
| `compare.context_used` | 有沒有找到高信心的過去 session |
| `compare.matched_sessions` | 高信心相關 session，可以拿來回答 |
| `compare.candidate_sessions` | 低信心候選，只能當提示，不能宣稱已參照 |

其餘欄位（`diagnostics`、`fallback_sessions`、`quality_flags`）細節在 `REFERENCE.md`，非必要不用看。

限制：這仍依賴 Copilot 的技能選擇器與模型自律，不是底層強制攔截。若平台提供真正的 message hook，應該直接在 hook 呼叫 `sync-copilot --compare`。

## 省 token：同一 session 內只需載入一次

- 這個 session 稍早已經注入過本檔案內容的話，之後不要重複整段貼出，只輸出一句提示（例如
  「（session-recall 已載入，執行 sync-copilot --compare）」），直接呼叫上面的核心指令。
- 只有換新 session、或使用者明確問起用法規則時，才重新完整讀一次本檔案。
- 需要完整功能（search / context-pack / graph / log-event / report / benchmark）或 FAQ 時，才用 view 讀 `REFERENCE.md`。

## 首次安裝（精簡版）

`~/SessionRecall/memory.sqlite` 不存在時，要先跟使用者說明：會建立哪些本機檔案、會讀取
`~\.copilot\session-store.db`、會匯入既有 session 摘要到 `~/SessionRecall`。取得同意才執行：

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.copilot\skills\session-recall\install.ps1"
```

其他安裝參數與分享規則見 `README.md` / `REFERENCE.md`，不重複列出。

## 建議操作流程

1. 觸發時先確認 `~/SessionRecall/memory.sqlite` 存在；不存在就走上面的首次安裝。
2. 已初始化 → 呼叫 `sync-copilot --compare "<current message>"`。
3. `context_used=true` → 簡短說明參照了哪些過去脈絡（1-2 個 `matched_sessions.title`）。
4. `context_used=false` → 說明沒找到明確相關歷史，不可把 `candidate_sessions` / `fallback_sessions` 說成已參照。
5. 其他需求對應：找相似內容 → `search`；當上下文 → `context-pack`；關聯圖 → `graph`（用法見 `REFERENCE.md`）。

## 需要更多細節時查閱

| 主題 | 位置 |
|---|---|
| 完整功能、指令一覽、compare/report 欄位 | `REFERENCE.md` |
| 驗證數據（命中率、省多少 token） | `docs/validation.md` |
| 與 session-to-memory 的分工、JSON 格式、輸出資料夾、FAQ | `REFERENCE.md` |
| 安裝參數細節、分享規則 | `README.md` / `REFERENCE.md` |
