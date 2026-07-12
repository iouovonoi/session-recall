#!/usr/bin/env python3
"""
Local-first Copilot session recall.

Stores session summaries as Markdown + JSON sidecars, indexes them in SQLite
FTS5, searches similar sessions locally, and emits a simple graph JSON.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(os.environ.get("SESSION_RECALL_HOME", Path.home() / "SessionRecall")).expanduser()
SESSIONS_DIR = ROOT / "sessions"
RAW_EVENTS_DIR = ROOT / "raw-events"
GRAPH_DIR = ROOT / "graph"
EXPORTS_DIR = ROOT / "exports"
DB_PATH = ROOT / "memory.sqlite"
STOP_TOKENS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "from",
    "目前",
    "這個",
    "那個",
    "我的",
    "你的",
    "之前",
    "相關",
    "內容",
    "討論",
    "是否",
    "以及",
    "哪些",
    "可以",
    "怎麼",
}
CJK_STOP_SUBSTRINGS = {
    "目前",
    "這個",
    "那個",
    "我的",
    "你的",
    "之前",
    "相關",
    "內容",
    "討論",
    "是否",
    "以及",
    "哪些",
    "可以",
    "怎麼",
}
GENERIC_DOMAIN_TOKENS = {"memory", "session", "local"}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:80] or "session"


def tokenize(value: str) -> set[str]:
    """Tokenize mixed English/Chinese text for lightweight local matching."""
    value = value.lower()
    words = set(re.findall(r"[a-z0-9_][a-z0-9_.:/-]{1,}", value, flags=re.UNICODE))
    for word in list(words):
        words.update(part for part in re.split(r"[-_./:]+", word) if len(part) >= 2)
    for sequence in re.findall(r"[\u4e00-\u9fff]+", value, flags=re.UNICODE):
        if 2 <= len(sequence) <= 4 and not is_cjk_noise(sequence):
            words.add(sequence)
        for size in range(2, 5):
            if len(sequence) >= size:
                words.update(
                    gram
                    for index in range(len(sequence) - size + 1)
                    for gram in [sequence[index : index + size]]
                    if not is_cjk_noise(gram)
                )
    return {word for word in words if word not in STOP_TOKENS}


def is_cjk_noise(token: str) -> bool:
    return any(stop in token for stop in CJK_STOP_SUBSTRINGS)


def ranked_tokens(value: str, limit: int = 48) -> list[str]:
    tokens = tokenize(value)
    return sorted(tokens, key=lambda item: (-len(item), item))[:limit]


def quote_fts_token(token: str) -> str:
    return '"' + token.replace('"', '""') + '"'


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                essence TEXT NOT NULL,
                summary TEXT NOT NULL,
                topics_json TEXT NOT NULL DEFAULT '[]',
                entities_json TEXT NOT NULL DEFAULT '[]',
                decisions_json TEXT NOT NULL DEFAULT '[]',
                open_questions_json TEXT NOT NULL DEFAULT '[]',
                content_path TEXT NOT NULL,
                json_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                importance INTEGER NOT NULL DEFAULT 3,
                last_accessed TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                turn_index INTEGER,
                compacted_at TEXT
            );

            DROP TABLE IF EXISTS session_fts;

            CREATE VIRTUAL TABLE session_fts USING fts5(
                session_id UNINDEXED,
                title,
                essence,
                summary,
                topics,
                entities
            );
            """
        )
        rows = conn.execute("SELECT * FROM sessions").fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT INTO session_fts(session_id, title, essence, summary, topics, entities)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["session_id"],
                    row["title"],
                    row["essence"],
                    row["summary"],
                    " ".join(json.loads(row["topics_json"])),
                    " ".join(json.loads(row["entities_json"])),
                ),
            )


def upsert_session(
    *,
    session_id: str,
    title: str,
    essence: str,
    summary: str,
    topics: list[str],
    entities: list[str],
    decisions: list[str] | None = None,
    open_questions: list[str] | None = None,
    content: str = "",
    importance: int = 3,
    created_at: str | None = None,
) -> dict:
    init_db()
    created_at = created_at or now_iso()
    decisions = decisions or []
    open_questions = open_questions or []
    md_path = SESSIONS_DIR / f"{session_id}.md"
    json_path = SESSIONS_DIR / f"{session_id}.summary.json"

    metadata = {
        "session_id": session_id,
        "title": title,
        "essence": essence,
        "summary": summary,
        "topics": topics,
        "entities": entities,
        "decisions": decisions,
        "open_questions": open_questions,
        "created_at": created_at,
        "updated_at": now_iso(),
        "importance": importance,
        "content_path": str(md_path),
    }

    md_path.write_text(render_session_markdown(metadata, content), encoding="utf-8")
    json_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO sessions (
                session_id, title, essence, summary, topics_json, entities_json,
                decisions_json, open_questions_json, content_path, json_path,
                created_at, updated_at, importance, last_accessed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                title,
                essence,
                summary,
                json.dumps(topics, ensure_ascii=False),
                json.dumps(entities, ensure_ascii=False),
                json.dumps(decisions, ensure_ascii=False),
                json.dumps(open_questions, ensure_ascii=False),
                str(md_path),
                str(json_path),
                created_at,
                metadata["updated_at"],
                importance,
                None,
            ),
        )
        conn.execute("DELETE FROM session_fts WHERE session_id = ?", (session_id,))
        conn.execute(
            """
            INSERT INTO session_fts(session_id, title, essence, summary, topics, entities)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, title, essence, summary, " ".join(topics), " ".join(entities)),
        )

    return {"ok": True, "session_id": session_id, "path": str(md_path)}


def add_session(args: argparse.Namespace) -> None:
    init_db()
    if args.json_file:
        payload = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        for key, value in payload.items():
            setattr(args, key.replace("-", "_"), value)

    created_at = args.created_at or now_iso()
    session_id = args.session_id or f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{slugify(args.title)}"
    topics = split_csv(args.topics)
    entities = split_csv(args.entities)
    decisions = split_csv(args.decisions)
    open_questions = split_csv(args.open_questions)
    content = args.content or ""

    result = upsert_session(
        session_id=session_id,
        title=args.title,
        essence=args.essence,
        summary=args.summary,
        topics=topics,
        entities=entities,
        decisions=decisions,
        open_questions=open_questions,
        content=content,
        importance=args.importance,
        created_at=created_at,
    )
    print(json.dumps(result, ensure_ascii=False))


def render_session_markdown(metadata: dict, content: str) -> str:
    lines = [
        f"# {metadata['title']}",
        "",
        f"- Session ID: `{metadata['session_id']}`",
        f"- Created: {metadata['created_at']}",
        f"- Essence: {metadata['essence']}",
        f"- Topics: {', '.join(metadata['topics']) or 'None'}",
        f"- Entities: {', '.join(metadata['entities']) or 'None'}",
        f"- Importance: {metadata['importance']}",
        "",
        "## Summary",
        "",
        metadata["summary"],
        "",
    ]
    if metadata["decisions"]:
        lines += ["## Decisions", "", *[f"- {item}" for item in metadata["decisions"]], ""]
    if metadata["open_questions"]:
        lines += ["## Open Questions", "", *[f"- {item}" for item in metadata["open_questions"]], ""]
    if content:
        lines += ["## Conversation Notes", "", content.strip(), ""]
    return "\n".join(lines)


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def log_event(args: argparse.Namespace) -> None:
    init_db()
    text = Path(args.text_file).read_text(encoding="utf-8") if args.text_file else (args.text or "")
    if not text.strip():
        raise SystemExit("ERROR: --text or --text-file is required")
    session_id = args.session_id or dt.datetime.now().strftime("%Y%m%d")
    created_at = args.created_at or now_iso()
    event_id = args.event_id or f"{session_id}-{dt.datetime.now().strftime('%H%M%S%f')}"
    event = {
        "event_id": event_id,
        "session_id": session_id,
        "role": args.role,
        "text": text,
        "created_at": created_at,
        "turn_index": args.turn_index,
    }

    raw_path = RAW_EVENTS_DIR / f"{session_id}.jsonl"
    with raw_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO events(event_id, session_id, role, text, created_at, turn_index, compacted_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (event_id, session_id, args.role, text, created_at, args.turn_index),
        )

    print(json.dumps({"ok": True, "event_id": event_id, "session_id": session_id, "path": str(raw_path)}, ensure_ascii=False))


def compact_events(args: argparse.Namespace) -> None:
    init_db()
    with connect() as conn:
        if args.session_id:
            session_ids = [args.session_id]
        else:
            rows = conn.execute(
                """
                SELECT session_id
                FROM events
                WHERE compacted_at IS NULL
                GROUP BY session_id
                ORDER BY MIN(created_at)
                LIMIT ?
                """,
                (args.limit,),
            ).fetchall()
            session_ids = [row["session_id"] for row in rows]

        compacted = []
        for session_id in session_ids:
            events = conn.execute(
                """
                SELECT * FROM events
                WHERE session_id = ? AND compacted_at IS NULL
                ORDER BY COALESCE(turn_index, 999999), created_at
                """,
                (session_id,),
            ).fetchall()
            if not events:
                continue

            content = "\n\n".join(f"{row['role']}: {row['text']}" for row in events)
            payload = summarize_events(session_id, events, content)
            result = upsert_session(**payload)
            timestamp = now_iso()
            conn.execute("UPDATE events SET compacted_at = ? WHERE session_id = ? AND compacted_at IS NULL", (timestamp, session_id))
            compacted.append(result)

    if args.graph and compacted:
        build_graph(argparse.Namespace())

    print(json.dumps({"ok": True, "compacted": compacted}, ensure_ascii=False, indent=2))


def summarize_events(session_id: str, events: list[sqlite3.Row], content: str) -> dict:
    first_user = next((row["text"] for row in events if row["role"] == "user"), events[0]["text"])
    title = first_line(first_user, 42)
    essence = first_line(first_user, 96)
    summary = make_summary(content)
    terms = sorted(tokenize(content), key=lambda item: (-content.lower().count(item), item))
    topics = [term for term in terms if len(term) >= 3][:8]
    entities = sorted(set(re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}\b", content)))[:12]
    created_at = events[0]["created_at"]
    return {
        "session_id": session_id,
        "title": title,
        "essence": essence,
        "summary": summary,
        "topics": topics,
        "entities": entities,
        "decisions": [],
        "open_questions": [],
        "content": content,
        "importance": 3,
        "created_at": created_at,
    }


def first_line(value: str, limit: int) -> str:
    line = re.sub(r"\s+", " ", value.strip()).strip()
    return line[:limit].rstrip() or "Untitled session"


def make_summary(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content.strip())
    if len(normalized) <= 900:
        return normalized
    return normalized[:900].rstrip() + "..."


def sync_copilot(args: argparse.Namespace) -> None:
    """Import Copilot CLI's native session-store.db into local searchable recall summaries."""
    init_db()
    source = Path(args.db_path) if args.db_path else Path.home() / ".copilot" / "session-store.db"
    if not source.exists():
        raise SystemExit(f"ERROR: Copilot session store not found: {source}")

    # Copy first so we do not hold locks against the running Copilot process.
    temp_path = Path(tempfile.gettempdir()) / f"copilot-session-store-{dt.datetime.now().strftime('%Y%m%d%H%M%S%f')}.db"
    shutil.copy2(source, temp_path)

    imported = []
    skipped_current = 0
    skipped_empty = 0
    native_total = 0
    try:
        native = sqlite3.connect(temp_path)
        native.row_factory = sqlite3.Row
        native_total = native.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        sessions = native.execute(
            """
            SELECT id, cwd, repository, branch, summary, created_at, updated_at
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()
        for session in sessions:
            turns = native.execute(
                """
                SELECT turn_index, user_message, assistant_response, timestamp
                FROM turns
                WHERE session_id = ?
                ORDER BY turn_index
                """,
                (session["id"],),
            ).fetchall()
            if not turns and not session["summary"]:
                skipped_empty += 1
                continue

            if not args.force and local_session_is_current(session["id"], session["updated_at"]):
                skipped_current += 1
                continue

            payload = summarize_copilot_session(session, turns)
            result = upsert_session(**payload)
            imported.append(result)
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass

    if args.graph and imported:
        build_graph(argparse.Namespace())

    local_total, fts_total = local_index_counts()
    sync_summary = {
        "source": str(source),
        "native_total": native_total,
        "limit": args.limit,
        "imported": len(imported),
        "skipped_current": skipped_current,
        "skipped_empty": skipped_empty,
        "local_total": local_total,
        "fts_total": fts_total,
    }
    output = {
        "ok": True,
        "source": str(source),
        "imported": len(imported),
        "sessions": imported,
        "indexed_total": local_total,
        "sync": sync_summary,
    }
    if args.report and not args.compare:
        raise SystemExit("ERROR: --report requires --compare to be set.")

    if args.compare:
        compare = compare_sessions(args.compare, args.compare_limit)
        output["similar"] = compare["matched_sessions"]
        output["compare"] = compare
        if args.report:
            output["report"] = build_report(compare, args.max_context_chars)
    print(json.dumps(output, ensure_ascii=False, indent=2))


def estimate_tokens(chars: int) -> int:
    """Rough, conservative token estimate: ceil(chars / 4). Not a real tokenizer."""
    if chars <= 0:
        return 0
    return -(-chars // 4)


def read_raw_session_content(item: dict) -> str:
    """Best-effort read of the full raw content backing a matched session.

    Falls back to title + essence + summary + topics when the on-disk
    markdown file is unavailable, so raw_context_chars always has a
    reasonable comparison baseline.
    """
    content_path = item.get("content_path")
    if content_path:
        try:
            text = Path(content_path).read_text(encoding="utf-8")
            if text.strip():
                return text
        except OSError:
            pass
    return " ".join(
        [
            item.get("title") or "",
            item.get("essence") or "",
            item.get("summary") or "",
            " ".join(item.get("topics") or []),
        ]
    )


def build_recommended_context(matched_sessions: list[dict], max_context_chars: int) -> tuple[list[dict], bool]:
    """Build the agent-facing precise context: high-confidence sessions only,
    metadata fields only (no raw turns), trimmed to fit max_context_chars.

    When the total exceeds the limit, the lowest-score session's summary is
    truncated first; if that is not enough, the lowest-score session is
    dropped entirely. Higher-score sessions are always kept over lower ones.
    """

    def entry_chars(entry: dict) -> int:
        return (
            len(entry["title"])
            + len(entry["essence"])
            + len(entry["summary"])
            + len(" ".join(entry["topics"]))
            + len(" ".join(entry["matched_terms"]))
            + len(entry["reason"])
        )

    items = [
        {
            "session_id": m["session_id"],
            "score": m["score"],
            "title": m["title"] or "",
            "essence": m["essence"] or "",
            "summary": m["summary"] or "",
            "topics": m.get("topics") or [],
            "matched_terms": m.get("matched_terms") or [],
            "reason": m.get("reason") or "",
        }
        for m in sorted(matched_sessions, key=lambda x: x["score"], reverse=True)
    ]

    truncated = False
    total = sum(entry_chars(entry) for entry in items)
    while items and total > max_context_chars:
        weakest = items[-1]
        excess = total - max_context_chars
        if len(weakest["summary"]) > 40:
            keep = max(0, len(weakest["summary"]) - (excess + 1))
            weakest["summary"] = weakest["summary"][:keep].rstrip() + "…"
            truncated = True
        else:
            items.pop()
            truncated = True
        total = sum(entry_chars(entry) for entry in items)

    for entry in items:
        entry.pop("score", None)
    return items, truncated


def build_report(compare: dict, max_context_chars: int) -> dict:
    matched_sessions = compare["matched_sessions"]
    recommended_context, truncated = build_recommended_context(matched_sessions, max_context_chars)

    raw_context_chars = sum(len(read_raw_session_content(item)) for item in matched_sessions)
    recommended_context_chars = sum(
        len(entry["title"]) + len(entry["essence"]) + len(entry["summary"]) + len(" ".join(entry["topics"])) + len(" ".join(entry["matched_terms"])) + len(entry["reason"])
        for entry in recommended_context
    )

    estimated_raw_tokens = estimate_tokens(raw_context_chars)
    estimated_recommended_tokens = estimate_tokens(recommended_context_chars)
    estimated_tokens_saved = max(0, estimated_raw_tokens - estimated_recommended_tokens)
    estimated_savings_percent = (
        round(estimated_tokens_saved / estimated_raw_tokens * 100, 1) if estimated_raw_tokens > 0 else 0.0
    )

    if not compare["context_used"]:
        estimated_tokens_saved = 0
        estimated_savings_percent = 0.0

    return {
        "recommended_context": recommended_context,
        "recommended_context_truncated": truncated,
        "max_context_chars": max_context_chars,
        "metrics": {
            "context_used": compare["context_used"],
            "matched_sessions_count": len(matched_sessions),
            "candidate_sessions_count": len(compare.get("candidate_sessions") or []),
            "raw_context_chars": raw_context_chars,
            "recommended_context_chars": recommended_context_chars,
            "estimated_raw_tokens": estimated_raw_tokens,
            "estimated_recommended_tokens": estimated_recommended_tokens,
            "estimated_tokens_saved": estimated_tokens_saved,
            "estimated_savings_percent": estimated_savings_percent,
        },
    }


def local_session_is_current(session_id: str, updated_at: str | None) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT updated_at FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    return bool(row and updated_at and row["updated_at"] >= updated_at)


def summarize_copilot_session(session: sqlite3.Row, turns: list[sqlite3.Row]) -> dict:
    user_texts = [row["user_message"] or "" for row in turns if row["user_message"]]
    assistant_texts = [row["assistant_response"] or "" for row in turns if row["assistant_response"]]
    first_user = user_texts[0] if user_texts else (session["summary"] or session["id"])
    title = first_line(session["summary"] or first_user, 64)
    essence = first_line(first_user, 140)

    content_parts = []
    for row in turns[:12]:
        if row["user_message"]:
            content_parts.append(f"user: {row['user_message']}")
        if row["assistant_response"]:
            content_parts.append(f"assistant: {row['assistant_response']}")
    content = "\n\n".join(content_parts)

    summary_source = session["summary"] or content
    summary = make_summary(summary_source)
    combined = " ".join([summary_source, content, session["cwd"] or "", session["repository"] or ""])
    terms = sorted(tokenize(combined), key=lambda item: (-combined.lower().count(item), item))
    topics = [term for term in terms if len(term) >= 3][:10]
    entities = sorted(set(re.findall(r"\b[A-Z][A-Za-z0-9_.:/-]{2,}\b", combined)))[:16]
    return {
        "session_id": session["id"],
        "title": title,
        "essence": essence,
        "summary": summary,
        "topics": topics,
        "entities": entities,
        "decisions": [],
        "open_questions": [],
        "content": content,
        "importance": 3,
        "created_at": session["created_at"] or now_iso(),
    }


def local_index_counts() -> tuple[int, int]:
    with connect() as conn:
        local_total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        fts_total = conn.execute("SELECT COUNT(*) FROM session_fts").fetchone()[0]
    return local_total, fts_total


def search_results(query: str, limit: int) -> list[dict]:
    return compare_sessions(query, limit)["matched_sessions"]


def compare_sessions(query: str, limit: int) -> dict:
    query = query.strip()
    query_tokens = ranked_tokens(query)
    query_token_set = set(query_tokens)
    results: dict[str, dict] = {}
    diagnostics = {
        "query_tokens": query_tokens,
        "query_token_count": len(query_token_set),
        "fts_hits": 0,
        "fallback_hits": 0,
        "local_total": 0,
        "fts_total": 0,
    }

    with connect() as conn:
        diagnostics["local_total"], diagnostics["fts_total"] = local_index_counts()
        fts_query = " OR ".join(quote_fts_token(token) for token in query_tokens[:32]) if query_tokens else query
        try:
            rows = conn.execute(
                """
                SELECT s.*, bm25(session_fts) AS bm25_score
                FROM session_fts
                JOIN sessions s ON s.session_id = session_fts.session_id
                WHERE session_fts MATCH ?
                LIMIT ?
                """,
                (fts_query, max(limit * 4, 10)),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            rows = []
            diagnostics["fts_error"] = str(exc)

        diagnostics["fts_hits"] = len(rows)
        for row in rows:
            item = scored_result(row, query_token_set, source="fts")
            if item["matched_terms"]:
                if len(item["matched_terms"]) == 1 and item["matched_terms"][0] in GENERIC_DOMAIN_TOKENS:
                    fts_boost = 0.08
                else:
                    fts_boost = 0.42 + min(len(item["matched_terms"]), 5) * 0.045
                item["score"] = max(item["score"], round(fts_boost, 3))
                apply_quality_adjustments(item, row)
                results[item["session_id"]] = item

        all_rows = conn.execute("SELECT * FROM sessions").fetchall()
        for row in all_rows:
            item = scored_result(row, query_token_set, source="token-overlap")
            apply_quality_adjustments(item, row)
            if item["matched_terms"] and item["score"] >= 0.06:
                diagnostics["fallback_hits"] += 1
                existing = results.get(item["session_id"])
                if existing and existing["score"] >= item["score"]:
                    existing["match_sources"] = sorted(set(existing["match_sources"] + item["match_sources"]))
                    existing["matched_terms"] = sorted(set(existing["matched_terms"] + item["matched_terms"]), key=lambda term: (-len(term), term))[:12]
                    continue
                results[item["session_id"]] = item

        ranked_all = [
            item
            for item in sorted(results.values(), key=lambda x: (x["score"], x["importance"], x["created_at"]), reverse=True)
            if item["score"] >= 0.1
        ]
        ranked = [item for item in ranked_all if item["score"] >= 0.3][:limit]
        candidate_sessions = [item for item in ranked_all if item["score"] < 0.3][:limit]
        diagnostics["low_confidence_candidates"] = len(candidate_sessions)
        if ranked:
            conn.executemany(
                "UPDATE sessions SET last_accessed = ? WHERE session_id = ?",
                [(now_iso(), item["session_id"]) for item in ranked],
            )
        fallback_sessions = []
        if not ranked:
            fallback_sessions = [
                row_to_result(row)
                for row in conn.execute("SELECT * FROM sessions ORDER BY updated_at DESC, created_at DESC LIMIT ?", (limit,)).fetchall()
            ]

    confidence = round(ranked[0]["score"], 3) if ranked else 0.0
    return {
        "query": query,
        "context_used": bool(ranked),
        "confidence": confidence,
        "matched_sessions": ranked,
        "candidate_sessions": candidate_sessions,
        "fallback_sessions": fallback_sessions,
        "diagnostics": diagnostics,
    }


def scored_result(row: sqlite3.Row, query_tokens: set[str], source: str) -> dict:
    fields = row_search_fields(row)
    all_text = " ".join(fields.values())
    text_tokens = tokenize(all_text)
    matched_terms = sorted(query_tokens & text_tokens, key=lambda term: (-len(term), term))[:12]
    coverage = len(matched_terms) / len(query_tokens) if query_tokens else 0.0
    density_boost = min(len(matched_terms), 10) * 0.025
    score = round(min(0.98, coverage * 0.82 + density_boost), 3)
    item = row_to_result(row)
    item["score"] = score
    item["matched_terms"] = matched_terms
    item["source_fields"] = matched_source_fields(fields, set(matched_terms))
    item["match_sources"] = [source]
    item["snippet"] = best_snippet(all_text, matched_terms)
    item["reason"] = make_match_reason(item["source_fields"], matched_terms)
    return item


def apply_quality_adjustments(item: dict, row: sqlite3.Row) -> None:
    flags = []
    if is_automation_like_session(row):
        item["score"] = round(item["score"] * 0.45, 3)
        flags.append("automation_like_session")
    item["quality_flags"] = flags


def is_automation_like_session(row: sqlite3.Row) -> bool:
    title = row["title"] or ""
    summary = row["summary"] or ""
    automation_markers = [
        "先讀取 SKILL 文件了解規範",
        "先讀取以下 SKILL 文件了解任務規範",
        "⚠️ 重要規則",
        "⚠️ 最 TOP 重要規則",
        "任務規範",
    ]
    haystack = f"{title}\n{summary}"
    return any(marker in haystack for marker in automation_markers)


def row_search_fields(row: sqlite3.Row) -> dict[str, str]:
    return {
        "title": row["title"],
        "essence": row["essence"],
        "summary": row["summary"],
        "topics": " ".join(json.loads(row["topics_json"])),
        "entities": " ".join(json.loads(row["entities_json"])),
    }


def matched_source_fields(fields: dict[str, str], matched_terms: set[str]) -> list[str]:
    source_fields = []
    for name, text in fields.items():
        tokens = tokenize(text)
        if matched_terms & tokens:
            source_fields.append(name)
    return source_fields


def best_snippet(text: str, matched_terms: list[str], window: int = 180) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ""
    lower = normalized.lower()
    positions = [lower.find(term.lower()) for term in matched_terms if lower.find(term.lower()) >= 0]
    if not positions:
        return normalized[:window].rstrip()
    start = max(min(positions) - 40, 0)
    snippet = normalized[start : start + window].rstrip()
    if start > 0:
        snippet = "..." + snippet
    if start + window < len(normalized):
        snippet += "..."
    return snippet


def make_match_reason(source_fields: list[str], matched_terms: list[str]) -> str:
    if not matched_terms:
        return "沒有明確 token 命中。"
    field_text = ", ".join(source_fields) if source_fields else "session metadata"
    term_text = ", ".join(matched_terms[:8])
    return f"在 {field_text} 命中相關詞：{term_text}"


def search(args: argparse.Namespace) -> None:
    init_db()
    print(json.dumps(search_results(args.query, args.limit), ensure_ascii=False, indent=2))


def row_to_result(row: sqlite3.Row) -> dict:
    return {
        "session_id": row["session_id"],
        "title": row["title"],
        "essence": row["essence"],
        "summary": row["summary"],
        "topics": json.loads(row["topics_json"]),
        "entities": json.loads(row["entities_json"]),
        "created_at": row["created_at"],
        "importance": row["importance"],
        "content_path": row["content_path"],
        "score": 0.0,
    }


def build_graph(_: argparse.Namespace) -> None:
    init_db()
    nodes: dict[str, dict] = {}
    edges: dict[tuple[str, str, str], dict] = {}

    def add_node(node_id: str, label: str, kind: str, **extra: object) -> None:
        nodes[node_id] = {"id": node_id, "label": label, "kind": kind, **extra}

    def add_edge(source: str, target: str, relation: str, weight: int = 1) -> None:
        key = (source, target, relation)
        if key not in edges:
            edges[key] = {"source": source, "target": target, "relation": relation, "weight": 0}
        edges[key]["weight"] += weight

    with connect() as conn:
        rows = conn.execute("SELECT * FROM sessions ORDER BY created_at").fetchall()

    for row in rows:
        sid = f"session:{row['session_id']}"
        quality_flags = ["automation_like_session"] if is_automation_like_session(row) else []
        add_node(
            sid,
            row["title"],
            "session",
            essence=row["essence"],
            created_at=row["created_at"],
            quality_flags=quality_flags,
        )
        for topic in json.loads(row["topics_json"]):
            tid = f"topic:{topic.lower()}"
            add_node(tid, topic, "topic")
            add_edge(sid, tid, "has_topic")
        for entity in json.loads(row["entities_json"]):
            eid = f"entity:{entity.lower()}"
            add_node(eid, entity, "entity")
            add_edge(sid, eid, "mentions")

    graph = {
        "generated_at": now_iso(),
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }
    output = GRAPH_DIR / "memory-graph.json"
    output.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(output), "nodes": len(nodes), "edges": len(edges)}, ensure_ascii=False))


def export_context(args: argparse.Namespace) -> None:
    init_db()
    query = args.query.strip()
    rows = []
    with connect() as conn:
        for row in conn.execute("SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (args.limit,)):
            haystack = f"{row['title']} {row['essence']} {row['summary']} {row['topics_json']} {row['entities_json']}"
            if not query or tokenize(query) & tokenize(haystack):
                rows.append(row_to_result(row))

    lines = [f"# Context Pack: {query or 'recent sessions'}", ""]
    for row in rows:
        lines += [
            f"## {row['title']}",
            "",
            f"- Session ID: `{row['session_id']}`",
            f"- Essence: {row['essence']}",
            f"- Topics: {', '.join(row['topics'])}",
            "",
            row["summary"],
            "",
        ]
    out = EXPORTS_DIR / f"context-pack-{slugify(query or 'recent')}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(out), "sessions": len(rows)}, ensure_ascii=False))


def benchmark(args: argparse.Namespace) -> None:
    """Run a local benchmark against a JSONL test set of {query, expected_session_ids, note}.

    This is a self-test / forum-post-screenshot tool only. It is not part of
    the normal recall workflow and is not run automatically.
    """
    init_db()
    jsonl_path = Path(args.jsonl_file)
    if not jsonl_path.exists():
        raise SystemExit(f"ERROR: benchmark JSONL file not found: {jsonl_path}")

    cases = []
    for line_number, raw_line in enumerate(jsonl_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"ERROR: invalid JSON on line {line_number} of {jsonl_path}: {exc}")
        if "query" not in case or not case["query"]:
            raise SystemExit(f"ERROR: line {line_number} of {jsonl_path} is missing a non-empty 'query' field")
        case.setdefault("expected_session_ids", [])
        cases.append(case)

    if not cases:
        raise SystemExit(f"ERROR: benchmark JSONL file has no usable rows: {jsonl_path}")

    max_context_chars = args.max_context_chars
    results = []
    hit_at_1 = 0
    hit_at_5 = 0
    context_used_count = 0
    savings_percents = []
    recommended_tokens_list = []

    for case in cases:
        query = case["query"]
        expected = set(case.get("expected_session_ids") or [])
        compare = compare_sessions(query, args.compare_limit)
        report = build_report(compare, max_context_chars)
        matched_ids = [item["session_id"] for item in compare["matched_sessions"]]

        case_hit_at_1 = bool(matched_ids) and matched_ids[0] in expected
        case_hit_at_5 = any(session_id in expected for session_id in matched_ids[:5])
        if case_hit_at_1:
            hit_at_1 += 1
        if case_hit_at_5:
            hit_at_5 += 1
        if compare["context_used"]:
            context_used_count += 1
        savings_percents.append(report["metrics"]["estimated_savings_percent"])
        recommended_tokens_list.append(report["metrics"]["estimated_recommended_tokens"])

        results.append(
            {
                "query": query,
                "note": case.get("note"),
                "expected_session_ids": sorted(expected),
                "matched_session_ids": matched_ids,
                "hit_at_1": case_hit_at_1,
                "hit_at_5": case_hit_at_5,
                "context_used": compare["context_used"],
                "estimated_savings_percent": report["metrics"]["estimated_savings_percent"],
            }
        )

    queries_total = len(cases)
    summary = {
        "queries_total": queries_total,
        "context_used_count": context_used_count,
        "hit_at_1": hit_at_1,
        "hit_at_5": hit_at_5,
        "hit_at_1_rate": round(hit_at_1 / queries_total, 3) if queries_total else 0.0,
        "hit_at_5_rate": round(hit_at_5 / queries_total, 3) if queries_total else 0.0,
        "average_estimated_savings_percent": round(sum(savings_percents) / queries_total, 1) if queries_total else 0.0,
        "average_recommended_context_tokens": round(sum(recommended_tokens_list) / queries_total, 1) if queries_total else 0.0,
    }
    print(json.dumps({"ok": True, "summary": summary, "results": results}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Local-first Copilot session recall")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init").set_defaults(func=lambda _args: (init_db(), print(str(DB_PATH))))

    add = sub.add_parser("add-session")
    add.add_argument("--json-file")
    add.add_argument("--session-id")
    add.add_argument("--title")
    add.add_argument("--essence")
    add.add_argument("--summary")
    add.add_argument("--topics", default="")
    add.add_argument("--entities", default="")
    add.add_argument("--decisions", default="")
    add.add_argument("--open-questions", default="")
    add.add_argument("--content", default="")
    add.add_argument("--created-at")
    add.add_argument("--importance", type=int, default=3)
    add.set_defaults(func=add_session)

    e = sub.add_parser("log-event")
    e.add_argument("--session-id")
    e.add_argument("--event-id")
    e.add_argument("--role", choices=["user", "assistant", "system"], default="user")
    e.add_argument("--text")
    e.add_argument("--text-file")
    e.add_argument("--created-at")
    e.add_argument("--turn-index", type=int)
    e.set_defaults(func=log_event)

    ce = sub.add_parser("compact-events")
    ce.add_argument("--session-id")
    ce.add_argument("--limit", type=int, default=20)
    ce.add_argument("--graph", action="store_true")
    ce.set_defaults(func=compact_events)

    sync = sub.add_parser("sync-copilot")
    sync.add_argument("--db-path")
    sync.add_argument("--limit", type=int, default=50)
    sync.add_argument("--force", action="store_true")
    sync.add_argument("--graph", action="store_true")
    sync.add_argument("--compare")
    sync.add_argument("--compare-limit", type=int, default=5)
    sync.add_argument("--report", action="store_true")
    sync.add_argument("--max-context-chars", type=int, default=2500)
    sync.set_defaults(func=sync_copilot)

    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=5)
    s.set_defaults(func=search)

    g = sub.add_parser("graph")
    g.set_defaults(func=build_graph)

    c = sub.add_parser("context-pack")
    c.add_argument("query", nargs="?", default="")
    c.add_argument("--limit", type=int, default=5)
    c.set_defaults(func=export_context)

    b = sub.add_parser("benchmark")
    b.add_argument("jsonl_file")
    b.add_argument("--compare-limit", type=int, default=5)
    b.add_argument("--max-context-chars", type=int, default=2500)
    b.set_defaults(func=benchmark)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
