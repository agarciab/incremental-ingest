DC=docker compose
APP=$(DC) run --rm app

up:
	$(DC) up -d

init:
	$(APP) python sample_docs.py
	$(APP) python -c "from opensearch_client import ensure_index; ensure_index(); print('index ready')"

ingest:
	$(APP) python ingest.py

search:
	$(APP) python search.py

mutate:
	$(APP) python mutate.py

delete-test:
	$(APP) python delete_test.py

verify:
	$(APP) python verify.py
