# Recall 效果驗證 / Validating Session Recall

這份文件回答兩件事：recall 有沒有真的找到相關內容？注入的 context 有沒有變小？
全部在本機跑，不上傳資料、不做遙測。

This doc answers two questions: does recall actually find relevant history, and does the injected
context shrink? Everything runs locally — no upload, no telemetry.

## 目前實測數值（參考基準） / Current observed values (reference snapshot)

> 來自一份真實本機索引（約 390 筆 session）+ 少量真實查詢，**僅供參考，不是保證值**，公開引用前請在自己的資料重新跑一次。
> Measured on one real local index (~390 sessions) with a small real query set. **Reference only, not
> guaranteed** — re-run on your own data before quoting publicly.

| 測試 Test | 命中/信心 Hit / confidence | 原始 → 建議注入 Raw → recommended | 省下 Savings |
|---|---|---|---|
| 單次 `--report`（查詢：「session recall 驗證功能 token 節省」） Single `--report` query | 2 個高信心 session 2 high-confidence matches | 18382 字 chars → 505 字 chars（≈4596 → 127 tokens） | **97.2%** |
| 3 筆查詢 `benchmark`（2 筆相關 + 1 筆刻意不相關） 3-query benchmark (2 relevant + 1 irrelevant) | `hit_at_1 = hit_at_5 = 2/3`（66.7%） | 平均 avg | **64.2%**（不相關查詢正確回報 0% correctly reports 0% when irrelevant） |

**結論 Takeaway**：有相關 session 時，省下幅度大致在 **60–97%**；沒有相關內容時，工具會老實說「沒找到」，不會硬湊分數。
When a relevant session exists, savings land around **60–97%**; when nothing is relevant, the tool
honestly reports no match instead of forcing a low-confidence result.

## 怎麼產生報告 / How to generate a report

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.copilot\skills\session-recall\scripts\session-recall.ps1" sync-copilot --limit 50 --compare "目前問題" --compare-limit 5 --report
```

- `--report` 一定要搭配 `--compare`，沒有就會報錯退出。`--report` always requires `--compare`, otherwise it errors out.
- `--max-context-chars`（預設 2500）限制 `recommended_context` 大小；超過時先截斷最低分 session 的摘要，還不夠才整個捨棄該 session，高分 session 永遠優先保留。
  `--max-context-chars` (default 2500) caps `recommended_context` size; the lowest-score session's summary is trimmed first, then dropped entirely if still too big — higher-score sessions are always kept.

## 欄位對照表 / Field reference

| 欄位 Field | 意思 Meaning |
|---|---|
| `context_used` | 有沒有找到高信心 session Whether a high-confidence match was found |
| `recommended_context` | 建議注入的精簡內容（title/essence/summary/topics/matched_terms/reason），不含完整對話原文 Trimmed metadata only, no raw turns |
| `raw_context_chars` / `estimated_raw_tokens` | 原始內容字數/估算 token Raw content size |
| `recommended_context_chars` / `estimated_recommended_tokens` | 建議注入內容字數/估算 token Recommended context size |
| `estimated_tokens_saved` / `estimated_savings_percent` | 省下多少；沒命中時一律 0 How much saved; always 0 when no match |

**token 估算只是粗估**：`估算 token = ceil(字數 / 4)`，不是真正的 tokenizer，中文密度可能不同，不能當作精準計費數字。
**Token estimate is rough only**: `estimated_tokens = ceil(chars / 4)`. Not a real tokenizer — don't
present it as exact billing cost.

## 自測用 benchmark / Self-test benchmark

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.copilot\skills\session-recall\scripts\session-recall.ps1" benchmark path\to\testset.jsonl
```

JSONL 每行一筆測試 / one test case per line:

```json
{"query": "問題文字", "expected_session_ids": ["session-id-1"], "note": "可選說明"}
```

| 輸出欄位 Output field | 意思 Meaning |
|---|---|
| `queries_total` | 測試題數 Number of test cases |
| `context_used_count` | 有命中的題數 Cases with a match |
| `hit_at_1` / `hit_at_5` | 命中第 1 名 / 前 5 名的題數 Correct in top-1 / top-5 |
| `average_estimated_savings_percent` | 平均省下比例 Average savings estimate |
| `average_recommended_context_tokens` | 平均注入內容大小 Average injected size |

只用於公開發文前自測/截圖，不建議放進一般流程；測試集用自己真實的查詢，公開分享前記得拿掉個人內容。
For self-testing / screenshots only, not part of normal usage — build the JSONL from your own real
queries and strip personal content before sharing publicly.

## 哪些宣稱合理、哪些不行 / What's a reasonable claim

| 可以說 OK to say | 不要說 Don't say |
|---|---|
| 「這組查詢裡，N% 找到高信心 session，注入內容約小了 X%（粗估）」 "For this query set, N% had a high-confidence match, and injected context was ~X% smaller (rough estimate)" | 「省下確切 N 個 token / N 元」 An exact token/dollar amount saved |
| 數字來自特定本機索引與測試集 Numbers are specific to one local index/test set | 這些數字適用所有情境或工作型態 These numbers generalize to all workloads |
| | 安裝人數或使用量（此工具不追蹤） Install/usage counts (not tracked) |
