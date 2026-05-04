from opensearch_client import client, INDEX
c = client()

def count(q):
    return c.count(index=INDEX, body={"query": q})['count']

total = count({"match_all": {}})
active = count({"term": {"status": "active"}})
phrase = c.search(index=INDEX, body={"query":{"match_phrase":{"content":"10k RPS sostinguts durant 30 minuts"}}})['hits']['total']['value']
deleted = count({"bool":{"must":[{"term":{"document_id":"criteris-daq"}},{"term":{"status":"deleted"}}]}})
vec = c.search(index=INDEX, body={"size":1,"query":{"knn":{"embedding":{"vector":[0.0]*384,"k":1}}}})['hits']['total']['value']
print({"total_docs": total, "active_chunks": active, "mutated_phrase_hits": phrase, "deleted_chunks": deleted, "vector_query_ok": vec >= 0})
