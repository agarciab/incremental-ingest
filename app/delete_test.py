from pathlib import Path
p = Path('/data/documents/criteris-daq.md')
if p.exists():
    p.unlink()
print('deleted criteris-daq.md')
