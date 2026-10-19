import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Solo raiz del bridge para que `import src.*` resuelva a AntaresBridge/src
for p in (str(ROOT),):
    if p not in sys.path:
        sys.path.insert(0, p)
# Asegura que AgendaSystem no opaque a bridge en este run
agenda = str(ROOT / "AgendaSystem")
if agenda in sys.path:
    sys.path.remove(agenda)
