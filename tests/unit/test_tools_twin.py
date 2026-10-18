"""Twin-drift guard for the soothe_client.tools dual copy.

``soothe_client/tools`` is a byte-identical twin of ``soothe_nano/tools``
(the canonical source, soothe-nano repo) except the self-import package
name. After nano changes, copy both files here and bump the pinned sha256
values here and in the nano-side twin test.

``__init__.py`` is hashed as-is; the nano copy is normalized
``soothe_nano`` → ``soothe_client`` before hashing, so the pin covers
everything except the import path.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[2] / "src" / "soothe_client" / "tools"
METADATA_SHA256 = "8e5b03d7a47ccf363f5052e593582922c45ece917032e0fa82377b3db9779147"
INIT_NORMALIZED_SHA256 = "85df3369f5c3595b3a76d2af382aded5afc1d15ab83dd7da59aa55103cbb7116"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_metadata_twin_is_pinned() -> None:
    digest = _sha256((TOOLS_DIR / "metadata.py").read_bytes())
    assert digest == METADATA_SHA256, (
        "tools/metadata.py diverged from the pinned nano twin — re-copy from "
        "soothe-nano src/soothe_nano/tools/metadata.py and update "
        "METADATA_SHA256 in BOTH twin tests"
    )


def test_init_twin_is_pinned_up_to_import_path() -> None:
    digest = _sha256((TOOLS_DIR / "__init__.py").read_bytes())
    assert digest == INIT_NORMALIZED_SHA256, (
        "tools/__init__.py diverged from the pinned nano twin (beyond the "
        "import path) — mirror it and update INIT_NORMALIZED_SHA256 in BOTH "
        "twin tests"
    )
