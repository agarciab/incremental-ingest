"""POC pipeline: tries CocoIndex import (for viability) and uses custom OpenSearch exporter."""
import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from embeddings import embed_texts, MODEL_NAME
from opensearch_client import client, INDEX

try:
    import cocoindex  # noqa: F401
    COCOINDEX_AVAILABLE = True
except Exception:
    COCOINDEX_AVAILABLE = False


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_chunks(text, size=420):
    parts, i = [], 0
    while i < len(text):
        parts.append(text[i:i+size])
        i += size
    return parts


def run_pipeline(data_dir, state_dir, pipeline_version="poc-v1"):
    now = datetime.now(timezone.utc).isoformat()
    state_path = Path(state_dir) / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(state_path.read_text()) if state_path.exists() else {}
    new = {}
    c = client()

    for f in sorted(Path(data_dir).glob("*")):
        if not f.is_file():
            continue
        txt = f.read_text(encoding="utf-8", errors="ignore")
        doc_id = f.stem
        doc_hash = sha(txt)
        new[doc_id] = {"path": str(f), "document_hash": doc_hash}
        if old.get(doc_id, {}).get("document_hash") == doc_hash:
            continue
        chunks = split_chunks(txt)
        vecs = embed_texts(chunks)
        c.delete_by_query(index=INDEX, body={"query": {"bool": {"must": [{"term": {"document_id": doc_id}}, {"term": {"status": "active"}}]}}}, conflicts="proceed", refresh=True)
        for i, (ch, vec) in enumerate(zip(chunks, vecs)):
            cid = f"{doc_id}::{i}::{sha(ch)[:10]}"
            body = {
                "chunk_id": cid, "document_id": doc_id, "source_path": str(f), "source_name": f.name,
                "content": ch, "embedding": vec, "section": "root", "chunk_index": i,
                "content_hash": sha(ch), "document_hash": doc_hash, "status": "active",
                "ingested_at": now, "updated_at": now, "parser": "markdown-text", "embedding_model": MODEL_NAME,
                "pipeline_version": pipeline_version,
            }
            c.index(index=INDEX, id=cid, body=body, refresh=True)

    removed = set(old.keys()) - set(new.keys())
    for doc_id in removed:
        c.update_by_query(index=INDEX, body={"query": {"term": {"document_id": doc_id}}, "script": {"source": "ctx._source.status='deleted'; ctx._source.updated_at=params.ts", "params": {"ts": now}}}, conflicts="proceed", refresh=True)

    state_path.write_text(json.dumps(new, indent=2))
    return {"cocoindex_available": COCOINDEX_AVAILABLE, "processed": len(new), "removed": list(removed)}
