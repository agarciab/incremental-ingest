# CocoIndex + OpenSearch POC — Ingesta incremental

Validació en local de CocoIndex com a motor d'ingesta incremental per alimentar OpenSearch per a RAG.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Compose                         │
│                                                             │
│  ┌──────────────────────┐    ┌──────────────────────────┐  │
│  │   app (Python 3.11)  │───▶│  opensearch:2.19.0       │  │
│  │                      │    │  port 9200               │  │
│  │  CocoIndex 1.0.3     │    │  índex: knowledge_chunks │  │
│  │  sentence-transform. │    │  knn: lucene / hnsw      │  │
│  │  opensearch-py 2.6   │    └──────────────────────────┘  │
│  └──────────────────────┘                                   │
│                                                             │
│  ┌──────────────────────┐                                   │
│  │  opensearch-dashboards│  port 5601 (opcional)           │
│  └──────────────────────┘                                   │
└─────────────────────────────────────────────────────────────┘
```

### Flux d'ingesta

```
/data/documents/*.md
        │
        ▼
CocoIndex: localfs.walk_dir()         ← escaneja fitxers
        │
        ▼
@coco.fn(memo=True) _process_file()   ← salta si el contingut no ha canviat
        │
        ├─ RecursiveSplitter (chunk_size=420, overlap=0)
        ├─ SentenceTransformerEmbedder (all-MiniLM-L6-v2, dim=384)
        ├─ delete_by_query (chunks actius del document)
        └─ bulk index → OpenSearch knowledge_chunks
                │
                ▼
        _mark_deleted()               ← soft-delete de fitxers eliminats del disc
```

L'estat incremental de CocoIndex es persisteix a SQLite (`/data/state/cocoindex.db`). El mecanisme `memo=True` detecta canvis per hash de contingut i re-processa únicament els fitxers modificats.

> CocoIndex no té connector natiu per a OpenSearch. L'export s'implementa directament dins de `@coco.fn(memo=True)`, que és el patró recomanat per a targets personalitzats.

---

## Índex OpenSearch: `knowledge_chunks`

| Camp | Tipus | Descripció |
|---|---|---|
| `chunk_id` | keyword | `doc_id::idx::hash[:10]` |
| `document_id` | keyword | Nom del fitxer sense extensió |
| `content` | text | Text del chunk (cerca BM25) |
| `embedding` | knn_vector(384) | Vector per cerca semàntica |
| `status` | keyword | `active` / `deleted` |
| `document_hash` | keyword | SHA-256 del fitxer sencer |
| `content_hash` | keyword | SHA-256 del chunk |
| `embedding_model` | keyword | `sentence-transformers/all-MiniLM-L6-v2` |
| `pipeline_version` | keyword | `poc-v1` |
| `ingested_at` / `updated_at` | date | Timestamps ISO-8601 UTC |

Motor KNN: `lucene`, algorisme `hnsw`, similitud `cosinesimil`.

---

## Prerequisits

- Docker o Podman + Compose
- Imatge `python:3.11-slim` disponible (si Docker Hub és inaccessible, es pot usar `mcr.microsoft.com/devcontainers/python:3.11` retaguejada)

---

## Execució

```bash
# 1. Arrancar serveis (espera que OpenSearch estigui healthy)
docker compose up -d

# 2. Crear documents de prova + índex
docker compose run --rm app python sample_docs.py
docker compose run --rm app python -c "from opensearch_client import ensure_index; ensure_index()"

# 3. Primera ingesta (processa tots els fitxers)
docker compose run --rm app python ingest.py

# 4. Cerca keyword i vectorial
docker compose run --rm app python search.py

# 5. Modificar un document i re-ingestar (incremental)
docker compose run --rm app python mutate.py
docker compose run --rm app python ingest.py

# 6. Eliminar un document i re-ingestar (soft-delete)
docker compose run --rm app python delete_test.py
docker compose run --rm app python ingest.py

# 7. Verificació final
docker compose run --rm app python verify.py
```

Si tens `make` disponible: `make up init ingest search mutate ingest delete-test ingest verify`

---

## Resultats de les proves

### Prova 1 — Ingesta inicial (3 documents)

Documents de prova en català sobre temes d'arquitectura:
- `guia-rendiment.md` — criteris P95, error rate, mTLS, proves de càrrega
- `criteris-daq.md` — revisió DAQ: arquitectura, SLA, rollback, OAuth2
- `apis-seguretat.md` — APIs REST: OAuth2/OIDC, rate limiting, mTLS

```
✅ _process_file: 3 total | 3 added
✅ _app_main:     1 total | 1 added
⏳ Elapsed: 13.9s
```

3 chunks indexats a OpenSearch, tots amb `status: active`.

---

### Prova 2 — Cerca keyword (BM25)

**Query:** `mTLS`

| Posició | Document | Score BM25 |
|---|---|---|
| 1 | `apis-seguretat` | 0.8447 |
| 2 | `guia-rendiment` | 0.7332 |

---

### Prova 3 — Cerca vectorial (semàntica)

**Query:** *"criteris per validar proves de càrrega abans de producció"*

| Posició | Document | Score cosinus |
|---|---|---|
| 1 | `guia-rendiment` | 0.7996 |
| 2 | `apis-seguretat` | 0.6550 |

El filtre `status=active` s'aplica dins del `knn` clause (pre-filtratge natiu d'OpenSearch ≥ 2.9).

---

### Prova 4 — Incrementalitat (modificació d'un document)

Afegida una frase a `guia-rendiment.md`. Segona execució d'ingesta:

```
✅ _process_file: 3 total | 1 reprocessed, 2 unchanged
⏳ Elapsed: 10.7s
```

CocoIndex detecta el canvi per hash de contingut i re-processa **únicament** el fitxer modificat. Els altres dos es salten sense cap operació a OpenSearch.

---

### Prova 5 — Eliminació d'un document (soft-delete)

Eliminat `criteris-daq.md` del disc. Tercera execució d'ingesta:

```
✅ _process_file: 3 total | 1 deleted, 2 unchanged
removed: ['criteris-daq']
```

El chunk queda a OpenSearch amb `status: deleted`. La cerca vectorial amb filtre `status=active` no el retorna:

**Query:** *"que cal revisar en un DAQ"* → `criteris-daq` no apareix als resultats (filtrat correctament).

---

### Prova 6 — Verificació final

```python
{
  'total_docs':          3,    # chunks totals a l'índex (actius + eliminats)
  'active_chunks':       2,    # guia-rendiment + apis-seguretat
  'mutated_phrase_hits': 1,    # frase afegida trobada per match_phrase
  'deleted_chunks':      1,    # criteris-daq marcat status=deleted
  'vector_query_ok':     True  # cerca vectorial retorna resultats
}
```

---

## Conclusions

| Aspecte | Resultat |
|---|---|
| Compatibilitat CocoIndex + OpenSearch | **Sí**, amb export custom via `@coco.fn(memo=True)` |
| Connector natiu OpenSearch a CocoIndex | No existeix — cal implementar-lo manualment |
| Incrementalitat per canvi de document | **Validada** — CocoIndex re-processa només el fitxer modificat |
| Soft-delete de documents eliminats | **Validat** — `status=deleted`, no retornat a les cerques |
| Cerca keyword BM25 | **Funcional** |
| Cerca vectorial semàntica (KNN) | **Funcional** amb filtre integrat |
| Estat incremental persistent | SQLite a `/data/state/cocoindex.db` (substitueix `state.json` manual) |

**Recomanació per a la següent fase:** integrar CocoIndex com a pipeline d'ingesta incremental de la plataforma agèntica, amb OpenSearch com a backend del Knowledge Service. El patró `@coco.fn(memo=True)` + export custom és suficient per al MVP; un connector natiu es pot considerar en fases posteriors si el volum documental ho requereix.
