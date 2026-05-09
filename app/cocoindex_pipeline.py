"""
CocoIndex + OpenSearch integration POC.

CocoIndex gestiona:
  - Detecció incremental de canvis de fitxers via @coco.fn(memo=True)
  - Escanejat de fitxers via localfs.walk_dir
  - Chunking via RecursiveSplitter
  - Embeddings via SentenceTransformerEmbedder
  - State DB intern (COCOINDEX_DB_PATH) — substitueix state.json

Export OpenSearch personalitzat:
  - CocoIndex no té connector natiu per a OpenSearch
  - Els chunks s'escriuen directament a OpenSearch dins de @coco.fn(memo=True)
  - Les eliminacions es gestionen amb un pas de cleanup posterior
"""
import hashlib
import os
import pathlib
from datetime import datetime, timezone
from typing import AsyncIterator

import cocoindex as coco
from cocoindex.connectors import localfs
from cocoindex.ops.sentence_transformers import SentenceTransformerEmbedder
from cocoindex.ops.text import RecursiveSplitter
from cocoindex.resources.file import FileLike, PatternFilePathMatcher
from opensearchpy.helpers import bulk

from opensearch_client import INDEX, client

DATA_DIR = os.getenv("DATA_DIR", "/data/documents")
PIPELINE_VERSION = os.getenv("PIPELINE_VERSION", "poc-v1")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

EMBEDDER = coco.ContextKey[SentenceTransformerEmbedder]("embedder", detect_change=True)

_splitter = RecursiveSplitter()


@coco.lifespan
async def _lifespan(builder: coco.EnvironmentBuilder) -> AsyncIterator[None]:
    builder.provide(EMBEDDER, SentenceTransformerEmbedder(EMBED_MODEL))
    yield


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@coco.fn(memo=True)
async def _process_file(file: FileLike) -> None:
    """Chunketja, embeds i fa upsert d'un fitxer a OpenSearch.

    Saltat automàticament per CocoIndex si el contingut del fitxer no ha canviat.
    """
    text = await file.read_text()
    doc_id = file.file_path.path.stem
    doc_hash = _sha(text)
    now = datetime.now(timezone.utc).isoformat()

    chunks = _splitter.split(text, chunk_size=420, chunk_overlap=0)
    embedder = coco.use_context(EMBEDDER)

    os_client = client()
    os_client.delete_by_query(
        index=INDEX,
        body={"query": {"bool": {"must": [
            {"term": {"document_id": doc_id}},
            {"term": {"status": "active"}},
        ]}}},
        conflicts="proceed",
        refresh=True,
    )

    actions = []
    for i, chunk in enumerate(chunks):
        embedding = await embedder.embed(chunk.text)
        cid = f"{doc_id}::{i}::{_sha(chunk.text)[:10]}"
        actions.append({
            "_index": INDEX,
            "_id": cid,
            "_source": {
                "chunk_id": cid,
                "document_id": doc_id,
                "source_path": str(pathlib.Path(DATA_DIR) / file.file_path.path),
                "source_name": file.file_path.path.name,
                "content": chunk.text,
                "embedding": embedding.tolist(),
                "section": "root",
                "chunk_index": i,
                "content_hash": _sha(chunk.text),
                "document_hash": doc_hash,
                "status": "active",
                "ingested_at": now,
                "updated_at": now,
                "parser": "markdown-text",
                "embedding_model": EMBED_MODEL,
                "pipeline_version": PIPELINE_VERSION,
            },
        })

    if actions:
        bulk(os_client, actions)
    os_client.indices.refresh(index=INDEX)


@coco.fn
async def _app_main(sourcedir: pathlib.Path) -> None:
    files = localfs.walk_dir(
        sourcedir,
        recursive=False,
        path_matcher=PatternFilePathMatcher(included_patterns=["**/*.md", "**/*.txt"]),
    )
    await coco.mount_each(_process_file, files.items())


_app = coco.App(
    coco.AppConfig(name="KnowledgeChunksFlow"),
    _app_main,
    sourcedir=pathlib.Path(DATA_DIR),
)


def _mark_deleted(data_dir: str) -> list[str]:
    """Soft-delete a OpenSearch els chunks de fitxers que ja no existeixen al disc."""
    os_client = client()
    now = datetime.now(timezone.utc).isoformat()

    resp = os_client.search(
        index=INDEX,
        body={
            "size": 0,
            "query": {"term": {"status": "active"}},
            "aggs": {"doc_ids": {"terms": {"field": "document_id", "size": 10_000}}},
        },
    )

    existing = {p.stem for p in pathlib.Path(data_dir).glob("*") if p.is_file()}
    removed = []
    for bucket in resp.get("aggregations", {}).get("doc_ids", {}).get("buckets", []):
        doc_id = bucket["key"]
        if doc_id not in existing:
            os_client.update_by_query(
                index=INDEX,
                body={
                    "query": {"bool": {"must": [
                        {"term": {"document_id": doc_id}},
                        {"term": {"status": "active"}},
                    ]}},
                    "script": {
                        "source": "ctx._source.status='deleted'; ctx._source.updated_at=params.ts",
                        "params": {"ts": now},
                    },
                },
                conflicts="proceed",
                refresh=True,
            )
            removed.append(doc_id)
    return removed


def run_pipeline(data_dir: str, state_dir: str, pipeline_version: str = "poc-v1") -> dict:
    """Executa la ingesta incremental.

    CocoIndex re-processa només els fitxers que han canviat (memo=True).
    Els fitxers eliminats del disc es marquen com 'deleted' a OpenSearch.
    """
    _app.update_blocking(report_to_stdout=True)
    removed = _mark_deleted(data_dir)
    return {
        "cocoindex_available": True,
        "pipeline": "cocoindex",
        "removed": removed,
    }
