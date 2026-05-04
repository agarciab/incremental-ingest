from pathlib import Path

DOCS = {
    "guia-rendiment.md": """# Guia de rendiment\nPer fer pas a PRE/PRO cal prova de càrrega, stress i soak.\n## Criteris\n- P95 < 350ms\n- error rate < 1%\n- CPU < 70%\nIncloure validació de mTLS als serveis crítics.\n""",
    "criteris-daq.md": """# Revisió DAQ\nAbans d'acceptar un DAQ cal revisar arquitectura, SLA, observabilitat i riscos.\nTambé revisar plans de rollback i compatibilitat amb OAuth2/OIDC.\n""",
    "apis-seguretat.md": """# APIs REST segures\nLes APIs REST han de requerir OAuth2/OIDC, rotació de secrets i mTLS intern.\nCal logging estructurat i controls de rate limiting abans de producció.\n""",
}


def create_docs(data_dir: str):
    p = Path(data_dir)
    p.mkdir(parents=True, exist_ok=True)
    for name, content in DOCS.items():
        (p / name).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    create_docs("/data/documents")
    print("sample docs created")
