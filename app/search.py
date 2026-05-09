from embeddings import embed_texts
from opensearch_client import INDEX, client


def keyword(q: str) -> dict:
    c = client()
    body = {
        "size": 5,
        "query": {"bool": {"must": [
            {"match": {"content": q}},
            {"term": {"status": "active"}},
        ]}},
    }
    return c.search(index=INDEX, body=body)


def semantic(q: str) -> dict:
    v = embed_texts([q])[0]
    c = client()
    body = {
        "size": 5,
        "query": {
            "knn": {
                "embedding": {
                    "vector": v,
                    "k": 5,
                    "filter": {"term": {"status": "active"}},
                }
            }
        },
    }
    return c.search(index=INDEX, body=body)


if __name__ == "__main__":
    queries = [
        ("mTLS", "keyword"),
        ("criteris per validar proves de càrrega abans de producció", "semantic"),
        ("què cal revisar en un DAQ", "semantic"),
    ]
    for q, t in queries:
        r = keyword(q) if t == "keyword" else semantic(q)
        print(f"\n== {t}: {q}")
        for h in r["hits"]["hits"]:
            print("-", h["_source"]["source_name"], h["_score"])
