from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


@dataclass
class ArtifactStore:
    """Accumulate named artifacts produced by workflow nodes."""

    _data: Dict[str, str] = field(default_factory=dict)

    def put(self, name: str, value: str) -> None:
        """Store or replace an artifact value."""
        self._data[name] = value

    def get(self, name: str) -> Optional[str]:
        """Return an artifact value if present."""
        return self._data.get(name)

    def to_context_block(self, artifact_names: Iterable[str]) -> str:
        """Format selected artifacts into a prompt-friendly context block."""
        lines: List[str] = []
        for name in artifact_names:
            value = self._data.get(name)
            if value:
                lines.append(f"[{name}]\n{value}\n")
        return "\n".join(lines) if lines else ""

    def all_keys(self) -> List[str]:
        """Return all stored artifact names."""
        return list(self._data.keys())
