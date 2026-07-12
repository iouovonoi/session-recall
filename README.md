# Session Recall

Session Recall 會讀取你自己的 `~\.copilot\session-store.db`，建立一個本機可搜尋的 session 索引，讓 Copilot CLI 可以回想相似的過去對話、匯出 context pack，並產生關聯圖。

Session Recall reads your own `~\.copilot\session-store.db` and builds a local, searchable session index so Copilot CLI can recall similar past conversations, export context packs, and generate a relationship graph.

所有資料都留在你的電腦上，不會由這個工具上傳。

Everything stays on your machine and is never uploaded by this tool.

## DeepWiki

你也可以在 DeepWiki 上閱讀自動產生的 repo 說明與架構導覽：

You can also read the auto-generated repo documentation and architecture guide on DeepWiki:

[DeepWiki: iouovonoi/session-recall](https://deepwiki.com/iouovonoi/session-recall)

## 實測概覽 / Results at a glance

以下數字來自一個真實本機索引的參考測試。完整說明請看 [session-recall/docs/validation.md](session-recall/docs/validation.md)。

The numbers below come from a real local reference index. See [session-recall/docs/validation.md](session-recall/docs/validation.md) for details.

| 指標 / Metric | 數值 / Value |
|---|---:|
| 找到相關 session 時節省的 context / Context saved when a relevant session is found | **60% to 97%** |
| 單次實測查詢 / One measured query | 18,382 chars to 505 chars, **97.2% saved** |
| 3 筆 benchmark 命中率 / 3-query benchmark hit rate | `hit@1 = hit@5 = 66.7%` |
| 找不到相關內容時 / When nothing relevant exists | 回報無匹配，不硬塞低信心結果 / Reports no match instead of forcing a low-confidence result |

## 先看哪份文件？/ Which doc should I read?

| 文件 / File | 適合對象 / Who it is for | 內容 / What is inside |
|---|---|---|
| **README.md** | 一般使用者 / General users | 安裝步驟、隱私規則、常用指令 / Install steps, privacy rules, common commands |
| **session-recall/REFERENCE.md** | 進階使用與排錯 / Power users and troubleshooting | 完整功能、JSON 格式、FAQ、內部設計 / Full feature list, JSON shape, FAQ, internals |
| **session-recall/docs/validation.md** | 想確認效果的人 / Anyone who wants proof it works | 報告與 benchmark 數字說明 / Report and benchmark numbers explained |
| **session-recall/SKILL.md** | Copilot CLI / agent | 觸發規則與使用方式 / Trigger rules and agent-facing instructions |

建議先讀 README；遇到問題或想看完整欄位時，再打開 `session-recall/REFERENCE.md`。

Start with this README. Open `session-recall/REFERENCE.md` when you need troubleshooting details or the full field reference.

## 安裝 / Install

把 repo 裡的 `session-recall` 資料夾複製到：

Copy the `session-recall` folder in this repo to:

```text
%USERPROFILE%\.copilot\skills\session-recall
```

重新啟動 Copilot CLI。第一次使用時，允許 agent 執行安裝，然後執行：

Restart Copilot CLI. On first use, approve the agent request, then run:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.copilot\skills\session-recall\install.ps1"
```

可選參數：

Optional flags:

| 需求 / Need | 參數 / Flag |
|---|---|
| 更改預設匯入 200 筆 session 的限制 / Change the default 200-session import limit | `-InitialSyncLimit 500` |
| 只建立空索引，不匯入資料 / Create an empty index and skip import | `-SkipInitialSync` |
| 每 30 分鐘自動同步 / Auto-sync every 30 minutes | `-InstallScheduler -EveryMinutes 30` |

## 測量 context 節省量 / Measuring context savings

使用 `--report` 可以確認 recall 是否找到相關歷史，以及建議注入的 context 是否變小。

Use `--report` to check whether recall finds relevant history and whether the injected context becomes smaller.

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.copilot\skills\session-recall\scripts\session-recall.ps1" sync-copilot --limit 50 --compare "session recall validation" --compare-limit 5 --report
```

如何解讀數字、哪些說法適合公開引用，請看 [session-recall/docs/validation.md](session-recall/docs/validation.md)。

For how to read the numbers and what is safe to claim publicly, see [session-recall/docs/validation.md](session-recall/docs/validation.md).

## 隱私 / Privacy

| 可以分享 / Share this | 不要分享 / Never share |
|---|---|
| skill 原始檔：`.md`, `.ps1`, `.py` / Skill source files | `~\SessionRecall` |
| 文件 / Documentation | `~\.copilot\session-store.db` |
| 已移除個資的截圖 / Screenshots with personal content removed | `~\.copilot\session-state` or other memory stores |

預設產生的資料都在 `~\SessionRecall`，這個工具不會把資料上傳。

Generated data stays under `~\SessionRecall` by default. This tool does not upload it.
