from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp", ".bmp", ".gif",
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".rw2", ".orf", ".pef", ".srw",
    ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".mts", ".m2ts", ".3gp", ".wmv",
}

SIDECAR_EXTENSIONS = {".xmp", ".aae", ".thm", ".lrv"}

SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}


@dataclass(frozen=True)
class ScannedFile:
    path: Path
    size: int
    is_media: bool
    is_sidecar: bool


def _classify(path: Path) -> tuple[bool, bool]:
    ext = path.suffix.lower()
    return ext in MEDIA_EXTENSIONS, ext in SIDECAR_EXTENSIONS


def scan(root: Path) -> Iterator[ScannedFile]:
    root = root.expanduser().resolve()
    for entry in root.rglob("*"):
        if not entry.is_file():
            continue
        if entry.name in SKIP_NAMES or entry.name.startswith("._"):
            continue
        is_media, is_sidecar = _classify(entry)
        try:
            size = entry.stat().st_size
        except OSError:
            continue
        yield ScannedFile(path=entry, size=size, is_media=is_media, is_sidecar=is_sidecar)


def scan_all(root: Path) -> list[ScannedFile]:
    return list(scan(root))
