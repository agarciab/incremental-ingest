from embeddings import embed_texts
from opensearch_client import INDEX, client

c = client()


def count(q: dict) -> int:
    return c.count(index=INDEX, body={"query": q})["count"]


total = count({"match_all": {}})
active = count({"term": {"status": "active"}})
phrase = c.search(
    index=INDEX,
    body={"query": {"match_phrase": {"content": "10k RPS sostinguts durant 30 minuts"}}},
)["hits"]["total"]["value"]
deleted = count({"bool": {"must": [
    {"term": {"document_id": "criteris-daq"}},
    {"term": {"status": "deleted"}},
]}})

# Cerca vectorial amb un embedding real en lloc d'un vector zero
test_vec = embed_texts(["rendiment i disponibilitat del sistema"])[0]
vec_hits = c.search(
    index=INDEX,
    body={
        "size": 1,
        "query": {
            "knn": {
                "embedding": {
                    "vector": test_vec,
                    "k": 1,
                    "filter": {"term": {"status": "active"}},
                }
            }
        },
    },
)["hits"]["total"]["value"]

print({
    "total_docs": total,
    "active_chunks": active,
    "mutated_phrase_hits": phrase,
    "deleted_chunks": deleted,
    "vector_query_ok": vec_hits >= 0,
})
