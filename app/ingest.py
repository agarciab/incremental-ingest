import os
from cocoindex_pipeline import run_pipeline
from opensearch_client import ensure_index

if __name__ == "__main__":
    ensure_index()
    result = run_pipeline(os.getenv("DATA_DIR", "/data/documents"), os.getenv("STATE_DIR", "/data/state"), os.getenv("PIPELINE_VERSION", "poc-v1"))
    print(result)
