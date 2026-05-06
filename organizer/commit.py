from __future__ import annotations

import hashlib
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from .planner import Manifest, PlannedEntry


def _hash_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.blake2b(digest_size=16)
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _copy_and_verify(entry: PlannedEntry) -> tuple[PlannedEntry, str | None]:
    src = Path(entry.source)
    dst = Path(entry.destination)
    try:
        if dst.exists() and dst.stat().st_size == entry.size:
            entry.status = "verified"
            return entry, None
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix(dst.suffix + ".part")
        shutil.copy2(src, tmp)
        if _hash_file(src) != _hash_file(tmp):
            tmp.unlink(missing_ok=True)
            return entry, "hash mismatch after copy"
        tmp.replace(dst)
        entry.status = "verified"
        return entry, None
    except Exception as e:
        return entry, str(e)


def _delete_source(entry: PlannedEntry) -> tuple[PlannedEntry, str | None]:
    try:
        Path(entry.source).unlink(missing_ok=True)
        entry.status = "committed"
        return entry, None
    except Exception as e:
        entry.status = "verified"
        return entry, str(e)


def execute(
    manifest: Manifest,
    console: Console,
    workers: int = 8,
    delete_source: bool = True,
    manifest_path: Path | None = None,
) -> tuple[int, int]:
    pending = [e for e in manifest.entries if e.status not in ("verified", "committed")]
    succeeded = 0
    failed = 0

    if not pending:
        console.print("[yellow]Nothing to do — manifest already complete.[/yellow]")
        return 0, 0

    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
    )

    with progress:
        task = progress.add_task("Copying + verifying", total=len(pending))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_copy_and_verify, e): e for e in pending}
            for fut in as_completed(futures):
                entry, err = fut.result()
                if err:
                    entry.status = "failed"
                    entry.error = err
                    failed += 1
                else:
                    succeeded += 1
                progress.advance(task)
                if manifest_path and (succeeded + failed) % 100 == 0:
                    manifest.save(manifest_path)

    if manifest_path:
        manifest.save(manifest_path)

    if not delete_source or failed > 0:
        if failed > 0:
            console.print(f"[red]{failed} file(s) failed — skipping source deletion for safety.[/red]")
        return succeeded, failed

    deletable = [e for e in manifest.entries if e.status == "verified"]
    with progress:
        task = progress.add_task("Removing originals", total=len(deletable))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_delete_source, e): e for e in deletable}
            for fut in as_completed(futures):
                entry, err = fut.result()
                if err:
                    entry.error = f"delete failed: {err}"
                progress.advance(task)

    if manifest_path:
        manifest.save(manifest_path)

    return succeeded, failed
