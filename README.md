# CocoIndex + OpenSearch POC (ingesta incremental)

## Objectiu
Validar en local si CocoIndex encaixa com a motor d'ingesta incremental per alimentar OpenSearch per RAG.

## Arquitectura local
- OpenSearch (index `knowledge_chunks`)
- OpenSearch Dashboards
- Servei Python (`app`) amb pipeline (`cocoindex_pipeline.py`) i exporter cap a OpenSearch.

## Nota sobre CocoIndex i target OpenSearch
Aquesta POC intenta usar CocoIndex (paquet Python instal·lat), però no s'ha utilitzat cap target natiu OpenSearch: s'ha implementat un **custom exporter mínim** que escriu directament a OpenSearch via `opensearch-py`.

## Prerequisits
- Docker + Docker Compose
- `make`

## Execució
```bash
docker compose up -d
make init
make ingest
make search
make mutate
make ingest
make delete-test
make ingest
make verify
```

## Incrementalitat i deletes
- Estat local a `data/state/state.json` (hash per document).
- Si canvia hash: es reindexa només aquell document.
- Si desapareix document: chunks marcats `status=deleted` amb `update_by_query`.

## Limitacions
- Parseig simple text/markdown (sense parser PDF avançat).
- Chunking fix per caràcters.
- Incrementalitat a nivell document (no diff de chunk intra-document).
- Cerca híbrida implementada com keyword + knn en consultes separades.

## Conclusions de la POC
- **Fit amb OpenSearch:** Sí, viable amb exporter custom.
- **Custom target necessari:** Sí en aquesta implementació.
- **Incrementalitat:** Real a nivell document, parcial a nivell chunk fi.
- **Model d'estat:** Acceptable per POC (hash local JSON), curt per producció.
- **Riscos tècnics:** consistència eventual en `delete_by_query/update_by_query`, necessitat d'orquestració i observabilitat més robusta.
- **Recomanació:** continuar investigant amb un connector natiu o framework CocoIndex més profund abans d'adopció plena.
