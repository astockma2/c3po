"""Kopiert den deutschen ReAct-Prompt-Override nach $OPENJARVIS_HOME/agents/.

Idempotent — laeuft mehrfach ohne Schaden. Wird in Stage 5 zum Setup
genutzt, damit der NativeReActAgent die deutsche Variante laedt statt
des englischen Default-Prompts.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "configs" / "c3po" / "agents" / "native_react" / "system_prompt.md"


def _dst_root() -> Path:
    return Path(os.environ.get("OPENJARVIS_HOME", "~/.openjarvis")).expanduser()


def main() -> int:
    if not SRC.exists():
        print(f"FEHLER: Quelle fehlt: {SRC}", file=sys.stderr)
        return 1
    dst = _dst_root() / "agents" / "native_react" / "system_prompt.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC, dst)
    print(f"OK: {SRC} -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
