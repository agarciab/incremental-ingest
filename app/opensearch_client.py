import os
from opensearchpy import OpenSearch

INDEX = os.getenv("OPENSEARCH_INDEX", "knowledge_chunks")


def client():
    return OpenSearch(hosts=[os.getenv("OPENSEARCH_URL", "http://localhost:9200")])


def ensure_index(dim=384):
    c = client()
    if c.indices.exists(INDEX):
        return
    body = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                "chunk_id": {"type": "keyword"},
                "document_id": {"type": "keyword"},
                "source_path": {"type": "keyword"},
                "source_name": {"type": "keyword"},
                "content": {"type": "text"},
                "embedding": {"type": "knn_vector", "dimension": dim, "method": {"name": "hnsw", "space_type": "cosinesimil", "engine": "lucene"}},
                "section": {"type": "keyword"},
                "chunk_index": {"type": "integer"},
                "content_hash": {"type": "keyword"},
                "document_hash": {"type": "keyword"},
                "status": {"type": "keyword"},
                "ingested_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "parser": {"type": "keyword"},
                "embedding_model": {"type": "keyword"},
                "pipeline_version": {"type": "keyword"},
            }
        },
    }
    c.indices.create(INDEX, body=body)
