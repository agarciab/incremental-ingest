from pathlib import Path
p = Path('/data/documents/guia-rendiment.md')
text = p.read_text(encoding='utf-8')
extra = "\nFrase verificable: ABANS DE PRO, validar test de càrrega de 10k RPS sostinguts durant 30 minuts.\n"
if extra not in text:
    p.write_text(text+extra, encoding='utf-8')
print('mutated')
