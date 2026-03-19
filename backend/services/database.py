import json
import aiosqlite
from pathlib import Path
from datetime import datetime

DB_PATH = str(Path(__file__).parent.parent / "aifc.db")

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
    return _db


async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS checks (
            id TEXT PRIMARY KEY,
            input_text TEXT NOT NULL,
            input_url TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS claim_results (
            id TEXT PRIMARY KEY,
            check_id TEXT NOT NULL,
            claim_text TEXT NOT NULL,
            subject TEXT DEFAULT '',
            claim_type TEXT DEFAULT 'other',
            status TEXT NOT NULL,
            reasoning TEXT DEFAULT '',
            confidence_score REAL DEFAULT 0.0,
            evidence_json TEXT DEFAULT '[]',
            decomposition_json TEXT,
            alignment_json TEXT,
            trace_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (check_id) REFERENCES checks(id)
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_result_id TEXT,
            trace_id TEXT,
            claim_id TEXT,
            claim_text TEXT,
            original_status TEXT,
            corrected_status TEXT,
            note TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_claim_results_check_id ON claim_results(check_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_claim_result_id ON feedback(claim_result_id);
    """)
    await db.commit()


async def close_db():
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def save_check(check_id: str, input_text: str, input_url: str | None, claims: list, results: list):
    db = await get_db()
    now = datetime.now().isoformat()

    await db.execute(
        "INSERT INTO checks (id, input_text, input_url, created_at) VALUES (?, ?, ?, ?)",
        (check_id, input_text, input_url, now),
    )

    for claim, result in zip(claims, results):
        claim_id = str(claim.claim_id) if hasattr(claim, "claim_id") else claim.get("claim_id", "")
        await db.execute(
            """INSERT INTO claim_results
               (id, check_id, claim_text, subject, claim_type, status, reasoning,
                confidence_score, evidence_json, decomposition_json, alignment_json, trace_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                claim_id,
                check_id,
                claim.claim_text if hasattr(claim, "claim_text") else claim.get("claim_text", ""),
                claim.subject if hasattr(claim, "subject") else claim.get("subject", ""),
                claim.claim_type if hasattr(claim, "claim_type") else claim.get("claim_type", "other"),
                result.status if hasattr(result, "status") else result.get("status", "NEI"),
                result.reasoning if hasattr(result, "reasoning") else result.get("reasoning", ""),
                result.confidence_score if hasattr(result, "confidence_score") else result.get("confidence_score", 0.0),
                json.dumps([e.model_dump() if hasattr(e, "model_dump") else e for e in (result.evidence_used if hasattr(result, "evidence_used") else result.get("evidence_used", []))]),
                json.dumps(result.decomposition if hasattr(result, "decomposition") else result.get("decomposition")) if (result.decomposition if hasattr(result, "decomposition") else result.get("decomposition")) else None,
                json.dumps(result.alignment.model_dump() if hasattr(result, "alignment") and result.alignment else result.get("alignment")) if (hasattr(result, "alignment") and result.alignment) or (isinstance(result, dict) and result.get("alignment")) else None,
                result.trace_id if hasattr(result, "trace_id") else result.get("trace_id", ""),
                now,
            ),
        )

    await db.commit()


async def save_feedback(trace_id: str, claim_id: str, claim_text: str, original_status: str, corrected_status: str, note: str | None):
    db = await get_db()
    await db.execute(
        """INSERT INTO feedback
           (claim_result_id, trace_id, claim_id, claim_text, original_status, corrected_status, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (claim_id, trace_id, claim_id, claim_text, original_status, corrected_status, note, datetime.now().isoformat()),
    )

    # Also update the claim_result status
    await db.execute(
        "UPDATE claim_results SET status = ? WHERE id = ? OR trace_id = ?",
        (corrected_status, claim_id, trace_id),
    )
    await db.commit()


async def get_history(limit: int = 20, offset: int = 0) -> dict:
    db = await get_db()

    total_row = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM checks")
    total = total_row[0][0]

    rows = await db.execute_fetchall(
        """SELECT c.id, c.input_text, c.input_url, c.created_at,
                  COUNT(cr.id) as claim_count,
                  SUM(CASE WHEN cr.status = 'SUPPORTED' THEN 1 ELSE 0 END) as supported_count,
                  SUM(CASE WHEN cr.status = 'REFUTED' THEN 1 ELSE 0 END) as refuted_count,
                  SUM(CASE WHEN cr.status = 'NEI' THEN 1 ELSE 0 END) as nei_count
           FROM checks c
           LEFT JOIN claim_results cr ON cr.check_id = c.id
           GROUP BY c.id
           ORDER BY c.created_at DESC
           LIMIT ? OFFSET ?""",
        (limit, offset),
    )

    items = []
    for row in rows:
        items.append({
            "id": row[0],
            "input_text": row[1],
            "input_url": row[2],
            "created_at": row[3],
            "claim_count": row[4] or 0,
            "supported_count": row[5] or 0,
            "refuted_count": row[6] or 0,
            "nei_count": row[7] or 0,
        })

    return {"items": items, "total": total}


async def get_check_detail(check_id: str) -> dict | None:
    db = await get_db()

    check_rows = await db.execute_fetchall(
        "SELECT id, input_text, input_url, created_at FROM checks WHERE id = ?",
        (check_id,),
    )
    if not check_rows:
        return None

    check = check_rows[0]
    result_rows = await db.execute_fetchall(
        """SELECT id, claim_text, subject, claim_type, status, reasoning,
                  confidence_score, evidence_json, decomposition_json, alignment_json, trace_id
           FROM claim_results WHERE check_id = ? ORDER BY created_at""",
        (check_id,),
    )

    claims = []
    results = []
    for row in result_rows:
        claims.append({
            "claim_id": row[0],
            "claim_text": row[1],
            "subject": row[2] or "",
            "is_checkable": True,
            "claim_type": row[3] or "other",
        })
        evidence = json.loads(row[7]) if row[7] else []
        decomposition = json.loads(row[8]) if row[8] else None
        alignment = json.loads(row[9]) if row[9] else None
        results.append({
            "claim_id": row[0],
            "trace_id": row[10] or "",
            "status": row[4],
            "reasoning": row[5] or "",
            "confidence_score": row[6] or 0.0,
            "decomposition": decomposition,
            "alignment": alignment,
            "evidence_used": evidence,
            "relevant_evidence_ids": [],
        })

    return {
        "id": check[0],
        "input_text": check[1],
        "input_url": check[2],
        "created_at": check[3],
        "claims": claims,
        "results": results,
    }
