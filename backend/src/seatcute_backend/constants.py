"""Pure, storage-agnostic constants and business-rule helpers (§4 of
_docs/specs.md). No SQLAlchemy or storage-layer imports here -- any store
implementation (in-memory, SQL, otherwise) builds on these same primitives.
"""

import re
import time
from typing import Optional

SIZES: tuple[int, ...] = (1, 2, 4, 6)
DEFAULT_COUNTS: dict[int, int] = {1: 2, 2: 4, 4: 3, 6: 1}
DEFAULT_TURNOVER: dict[int, int] = {1: 30, 2: 45, 4: 60, 6: 90}

_LABEL_INDEX_RE = re.compile(r"#(\d+)$")


def now_ms() -> int:
    return int(time.time() * 1000)


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def label_index(label: str) -> int:
    match = _LABEL_INDEX_RE.search(label)
    return int(match.group(1)) if match else 0


def map_party_size_to_queue_size(party_size: int) -> Optional[int]:
    fits = [s for s in SIZES if s >= party_size]
    return min(fits) if fits else None
