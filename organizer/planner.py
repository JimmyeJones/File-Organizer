from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

from .metadata import FileMeta, UNKNOWN_CAMERA
from .scan import ScannedFile

MONTH_NAMES = [
    "01-January", "02-February", "03-March", "04-April", "05-May", "06-June",
    "07-July", "08-August", "09-September", "10-October", "11-November", "12-December",
]

SCHEMES = {
    "year-month-camera": ("Year / Month / Camera", ("year", "month", "camera")),
    "year-camera-month": ("Year / Camera / Month", ("year", "camera", "month")),
    "camera-year-month": ("Camera / Year / Month", ("camera", "year", "month")),
}
DEFAULT_SCHEME = "year-month-camera"


@dataclass
class PlannedEntry:
    source: str
    destination: str
    size: int
    kind: str  # "media" | "sidecar" | "non-media"
    camera: str = ""
    taken: str = ""  # ISO date or ""
    status: str = "planned"  # planned | copied | verified | committed | failed | skipped
    error: str = ""


@dataclass
class Manifest:
    source_root: str
    dest_root: str
    created_at: str
    entries: list[PlannedEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_root": self.source_root,
            "dest_root": self.dest_root,
            "created_at": self.created_at,
            "entries": [asdict(e) for e in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        return cls(
            source_root=data["source_root"],
            dest_root=data["dest_root"],
            created_at=data["created_at"],
            entries=[PlannedEntry(**e) for e in data.get("entries", [])],
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        return cls.from_dict(json.loads(path.read_text()))


def _media_dest(
    dest_root: Path,
    taken: datetime | None,
    camera: str,
    name: str,
    scheme: str = DEFAULT_SCHEME,
) -> Path:
    if scheme not in SCHEMES:
        scheme = DEFAULT_SCHEME
    _, order = SCHEMES[scheme]

    parts: dict[str, str] = {
        "year": f"{taken.year:04d}" if taken else "Unknown-Date",
        "month": MONTH_NAMES[taken.month - 1] if taken else "Unknown-Month",
        "camera": camera or "Unknown-Camera",
    }
    if taken is None:
        # Collapse to Unknown-Date/<camera>/file regardless of scheme
        return dest_root / "media" / "Unknown-Date" / parts["camera"] / name
    return dest_root / "media" / Path(*[parts[p] for p in order]) / name


def _resolve_conflict(used: set[Path], dest: Path) -> Path:
    if dest not in used:
        used.add(dest)
        return dest
    stem, suffix = dest.stem, dest.suffix
    i = 1
    while True:
        candidate = dest.with_name(f"{stem}_{i}{suffix}")
        if candidate not in used:
            used.add(candidate)
            return candidate
        i += 1


def build_manifest(
    source_root: Path,
    dest_root: Path,
    scanned: list[ScannedFile],
    metas: dict[Path, FileMeta],
    scheme: str = DEFAULT_SCHEME,
) -> Manifest:
    source_root = source_root.expanduser().resolve()
    dest_root = dest_root.expanduser().resolve()

    by_dir_stem: dict[tuple[Path, str], list[ScannedFile]] = defaultdict(list)
    for f in scanned:
        by_dir_stem[(f.path.parent, f.path.stem)].append(f)

    media_files = [f for f in scanned if f.is_media]
    media_keys = {(f.path.parent, f.path.stem) for f in media_files}

    used_destinations: set[Path] = set()
    entries: list[PlannedEntry] = []

    for f in media_files:
        meta = metas.get(f.path)
        camera = meta.camera if meta else UNKNOWN_CAMERA
        taken = meta.taken if meta else None
        dest = _media_dest(dest_root, taken, camera, f.path.name, scheme)
        dest = _resolve_conflict(used_destinations, dest)
        entries.append(PlannedEntry(
            source=str(f.path),
            destination=str(dest),
            size=f.size,
            kind="media",
            camera=camera,
            taken=taken.isoformat() if taken else "",
        ))

        for sib in by_dir_stem[(f.path.parent, f.path.stem)]:
            if sib.path == f.path or not sib.is_sidecar:
                continue
            sib_dest = dest.with_suffix(sib.path.suffix)
            sib_dest = _resolve_conflict(used_destinations, sib_dest)
            entries.append(PlannedEntry(
                source=str(sib.path),
                destination=str(sib_dest),
                size=sib.size,
                kind="sidecar",
                camera=camera,
                taken=taken.isoformat() if taken else "",
            ))

    for f in scanned:
        if f.is_media:
            continue
        if f.is_sidecar and (f.path.parent, f.path.stem) in media_keys:
            continue
        try:
            rel = f.path.relative_to(source_root)
        except ValueError:
            rel = Path(f.path.name)
        dest = dest_root / "non-media" / rel
        dest = _resolve_conflict(used_destinations, dest)
        entries.append(PlannedEntry(
            source=str(f.path),
            destination=str(dest),
            size=f.size,
            kind="non-media",
        ))

    return Manifest(
        source_root=str(source_root),
        dest_root=str(dest_root),
        created_at=datetime.now().isoformat(timespec="seconds"),
        entries=entries,
    )
