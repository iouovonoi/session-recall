# 驗證 Session Recall / Validating Session Recall

這份文件回答兩個問題：recall 是否真的找到相關歷史？建議注入的 context 是否比 raw context 小？

This document answers two questions: does recall actually find relevant history, and is the recommended injected context smaller than raw context?

所有測試都在本機執行，不上傳、不遙測。

Everything runs locally with no upload and no telemetry.

## 目前觀察值 / Current Observed Values

以下數字來自一個真實本機索引與小型查詢集，只能當作參考。公開引用前，請在自己的資料上重跑。

The numbers below come from one real local index and a small query set. Treat them as reference values only. Re-run on your own data before quoting them publicly.

| 測試 / Test | 命中與信心 / Hit and confidence | Raw to recommended | 節省 / Savings |
|---|---|---:|---:|
| 單次 `--report` 查詢 / Single `--report` query | 2 個高信心匹配 / 2 high-confidence matches | 18,382 chars to 505 chars | **97.2%** |
| 3 筆 `benchmark` / 3-query benchmark | `hit_at_1 = hit_at_5 = 2/3` | average | **64.2%** |

重點：有相關 session 時，建議 context 通常明顯小於 raw context；沒有相關內容時，工具應回報無匹配，而不是硬塞低信心結果。

Takeaway: when relevant sessions exist, recommended context is usually much smaller than raw context. When nothing relevant exists, the tool should report no match instead of forcing a low-confidence result.

## 產生 report / How to Generate a Report

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.copilot\skills\session-recall\scripts\session-recall.ps1" sync-copilot --limit 50 --compare "session recall validation" --compare-limit 5 --report
```

- `--report` 必須搭配 `--compare`，否則會報錯。
- `--report` always requires `--compare`; otherwise it errors.
- `--max-context-chars` 預設是 `2500`，會限制 `recommended_context` 的大小。
- `--max-context-chars` defaults to `2500` and caps the size of `recommended_context`.

## 欄位參考 / Field Reference

| 欄位 / Field | 意義 / Meaning |
|---|---|
| `context_used` | 是否找到高信心匹配 / Whether a high-confidence match was found |
| `recommended_context` | 建議注入的精簡 metadata，不含完整 raw turns / Trimmed metadata only, without full raw turns |
| `raw_context_chars` / `estimated_raw_tokens` | raw context 的大小與粗略 token 估算 / Raw context size and rough token estimate |
| `recommended_context_chars` / `estimated_recommended_tokens` | 建議 context 的大小與粗略 token 估算 / Recommended context size and rough token estimate |
| `estimated_tokens_saved` / `estimated_savings_percent` | 估計節省量；無匹配時為 0 / Estimated savings; 0 when there is no match |

token 估算公式是 `ceil(chars / 4)`。這只是粗估，不是精準計費或 tokenizer 結果。

The token estimate is `ceil(chars / 4)`. It is only a rough estimate, not exact billing or tokenizer output.

## 自測 benchmark / Self-Test Benchmark

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.copilot\skills\session-recall\scripts\session-recall.ps1" benchmark path\to\testset.jsonl
```

JSONL 每行一筆測試：

One test case per JSONL line:

```json
{"query": "session recall validation", "expected_session_ids": ["session-id-1"], "note": "known relevant session"}
```

| 輸出欄位 / Output field | 意義 / Meaning |
|---|---|
| `queries_total` | 測試筆數 / Number of test cases |
| `context_used_count` | 有找到匹配的案例數 / Cases with a match |
| `hit_at_1` / `hit_at_5` | top-1 / top-5 是否命中預期 session / Correct in top-1 or top-5 |
| `average_estimated_savings_percent` | 平均估計節省比例 / Average estimated savings |
| `average_recommended_context_tokens` | 平均建議注入 token 數 / Average recommended context tokens |

benchmark 適合自測或截圖，不是正常使用流程的一部分。分享前請移除個人內容。

The benchmark is for self-testing or screenshots. It is not part of normal usage. Strip personal content before sharing.

## 合理說法 / Reasonable Claims

| 可以說 / OK to say | 不要說 / Do not say |
|---|---|
| 「在這組查詢中，N% 有高信心匹配，建議 context 約少 X%。」 / "For this query set, N% had high-confidence matches and injected context was about X% smaller." | 「一定能省 N tokens 或 N 元。」 / "It always saves exactly N tokens or N dollars." |
| 「數字依本機索引與測試集而變。」 / "Numbers depend on the local index and query set." | 「這些數字可泛化到所有使用者。」 / "These numbers generalize to all users." |
| 「此工具不追蹤安裝數或使用數。」 / "This tool does not track installs or usage." | 「有全域使用統計。」 / "There are global usage stats." |
