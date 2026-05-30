"""Incident memory store: persist incident embeddings and run cosine similarity recall.

Embeddings are produced by the agent (which owns the OpenAI/Ollama client). The backend
only stores the vectors and ranks them — it never calls an embedding provider itself.
SQLite-friendly: vectors live as JSON blobs and similarity is computed in Python, which is
fine at homelab scale (hundreds–low-thousands of incidents).
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

from ..models.incident import IncidentEmbedding


def _cosine(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def store_incident(db, *, ip, port, scan_id, vector, summary,
                   source='verdict', embedding_model=None) -> dict:
    """Insert one incident embedding. Idempotent per (scan_id, ip, port, source)."""
    if not vector:
        return {'status': 'skipped', 'reason': 'empty vector'}

    existing = None
    if scan_id is not None:
        existing = (
            IncidentEmbedding.query
            .filter_by(scan_id=scan_id, ip=ip, port=port, source=source)
            .first()
        )
    if existing:
        existing.summary = summary
        existing.vector_json = json.dumps(vector)
        existing.embedding_model = embedding_model
        db.session.commit()
        return {'status': 'updated', 'id': existing.id}

    row = IncidentEmbedding(
        ip=ip,
        port=port,
        scan_id=scan_id,
        source=source,
        summary=summary,
        embedding_model=embedding_model,
        vector_json=json.dumps(vector),
    )
    db.session.add(row)
    db.session.commit()
    return {'status': 'stored', 'id': row.id}


def search_similar(db, *, vector, days=90, top_k=5, min_score=0.0,
                   exclude_scan_id=None) -> list:
    """Return up to top_k stored incidents most similar to `vector`, newest-window first."""
    if not vector:
        return []

    cutoff = datetime.utcnow() - timedelta(days=days)
    q = IncidentEmbedding.query.filter(IncidentEmbedding.created_at >= cutoff)
    if exclude_scan_id is not None:
        q = q.filter(IncidentEmbedding.scan_id != exclude_scan_id)

    scored = []
    for row in q.all():
        score = _cosine(vector, row.vector())
        if score < min_score:
            continue
        d = row.as_dict()
        d['score'] = round(score, 4)
        scored.append(d)

    scored.sort(key=lambda d: d['score'], reverse=True)
    return scored[:top_k]
