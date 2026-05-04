from embeddings import embed_texts
from opensearch_client import client, INDEX

c = client()

def keyword(q):
    body={"size":5,"query":{"bool":{"must":[{"match":{"content":q}},{"term":{"status":"active"}}]}}}
    return c.search(index=INDEX, body=body)

def semantic(q):
    v = embed_texts([q])[0]
    body={"size":5,"query":{"bool":{"must":[{"knn":{"embedding":{"vector":v,"k":5}}},{"term":{"status":"active"}}]}}}
    return c.search(index=INDEX, body=body)

if __name__ == '__main__':
    for q,t in [("mTLS","keyword"),("criteris per validar proves de càrrega abans de producció","semantic"),("què cal revisar en un DAQ","semantic")]:
        r = keyword(q) if t=="keyword" else semantic(q)
        print(f"\n== {t}: {q}")
        for h in r['hits']['hits']:
            print('-',h['_source']['source_name'], h['_score'])
