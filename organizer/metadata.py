from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

try:
    import exiftool  # type: ignore
except ImportError:
    exiftool = None  # type: ignore


DATE_TAG_PRIORITY = [
    "EXIF:DateTimeOriginal",
    "QuickTime:CreateDate",
    "QuickTime:MediaCreateDate",
    "EXIF:CreateDate",
    "XMP:DateCreated",
    "Composite:SubSecDateTimeOriginal",
    "File:FileModifyDate",
]

MAKE_TAGS = ["EXIF:Make", "QuickTime:Make", "XMP:Make"]
MODEL_TAGS = ["EXIF:Model", "QuickTime:Model", "XMP:Model"]

UNKNOWN_CAMERA = "Unknown-Camera"

_DATE_RE = re.compile(r"(\d{4})[:\-](\d{2})[:\-](\d{2})[ T](\d{2}):(\d{2}):(\d{2})")


@dataclass(frozen=True)
class FileMeta:
    path: Path
    taken: datetime | None
    camera: str
    raw: dict


def exiftool_available() -> bool:
    return exiftool is not None and shutil.which("exiftool") is not None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    m = _DATE_RE.search(str(value))
    if not m:
        return None
    try:
        return datetime(*(int(g) for g in m.groups()))
    except ValueError:
        return None


def _sanitize(part: str) -> str:
    part = part.strip()
    part = re.sub(r"[\\/<>:\"|?*\x00-\x1f]", "", part)
    part = re.sub(r"\s+", "-", part)
    return part or ""


def _camera_name(meta: dict) -> str:
    make = next((meta.get(t) for t in MAKE_TAGS if meta.get(t)), "")
    model = next((meta.get(t) for t in MODEL_TAGS if meta.get(t)), "")
    make_s = _sanitize(str(make)) if make else ""
    model_s = _sanitize(str(model)) if model else ""
    if make_s and model_s and not model_s.lower().startswith(make_s.lower()):
        return f"{make_s}-{model_s}"
    return model_s or make_s or UNKNOWN_CAMERA


def _date_from_meta(meta: dict) -> datetime | None:
    for tag in DATE_TAG_PRIORITY:
        d = _parse_date(meta.get(tag))
        if d:
            return d
    return None


def _fallback_meta(path: Path) -> FileMeta:
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        mtime = None
    return FileMeta(path=path, taken=mtime, camera=UNKNOWN_CAMERA, raw={})


def extract_batch(paths: list[Path]) -> dict[Path, FileMeta]:
    if not paths:
        return {}
    if not exiftool_available():
        return {p: _fallback_meta(p) for p in paths}

    results: dict[Path, FileMeta] = {}
    with exiftool.ExifToolHelper() as et:  # type: ignore[union-attr]
        try:
            metas = et.get_metadata([str(p) for p in paths])
        except Exception:
            return {p: _fallback_meta(p) for p in paths}

    by_source = {Path(m.get("SourceFile", "")).resolve(): m for m in metas}
    for p in paths:
        m = by_source.get(p.resolve()) or by_source.get(p)
        if not m:
            results[p] = _fallback_meta(p)
            continue
        taken = _date_from_meta(m)
        if taken is None:
            try:
                taken = datetime.fromtimestamp(p.stat().st_mtime)
            except OSError:
                taken = None
        results[p] = FileMeta(path=p, taken=taken, camera=_camera_name(m), raw=m)
    return results


def chunked(items: list, size: int) -> Iterable[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
