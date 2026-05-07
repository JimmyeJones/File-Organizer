from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.prompt import Confirm, Prompt

from .commit import execute
from .metadata import FileMeta, chunked, exiftool_available, extract_batch
from .planner import DEFAULT_SCHEME, SCHEMES, Manifest, build_manifest
from .preview import render_summary, render_tree
from .scan import ScannedFile, scan


def _progress(console: Console) -> Progress:
    return Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
    )


def _scan_with_progress(console: Console, source: Path) -> list[ScannedFile]:
    files: list[ScannedFile] = []
    with console.status(f"[bold blue]Scanning {source}...[/bold blue]", spinner="dots"):
        for f in scan(source):
            files.append(f)
    console.print(f"[green]✓[/green] Found {len(files)} files")
    return files


def _extract_with_progress(
    console: Console, files: list[ScannedFile], workers: int, batch_size: int
) -> dict[Path, FileMeta]:
    media = [f.path for f in files if f.is_media]
    if not media:
        return {}

    if not exiftool_available():
        console.print(
            "[yellow]![/yellow] exiftool not found — falling back to file mtime + Unknown-Camera. "
            "Install exiftool for better results."
        )

    metas: dict[Path, FileMeta] = {}
    batches = list(chunked(media, batch_size))

    with _progress(console) as progress:
        task = progress.add_task("Reading metadata", total=len(media))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(extract_batch, b) for b in batches]
            for fut in as_completed(futures):
                result = fut.result()
                metas.update(result)
                progress.advance(task, advance=len(result))
    return metas


def _interactive_scheme(console: Console, preset: str | None) -> str:
    if preset:
        return preset
    console.print()
    console.print("[bold]Choose folder scheme:[/bold]")
    keys = list(SCHEMES.keys())
    for i, key in enumerate(keys, 1):
        label, _ = SCHEMES[key]
        example_parts = []
        sample = {"year": "2024", "month": "03-March", "camera": "Canon-EOS-R5"}
        _, order = SCHEMES[key]
        example = "/".join(sample[p] for p in order) + "/IMG_1234.jpg"
        marker = " (default)" if key == DEFAULT_SCHEME else ""
        console.print(f"  [cyan]{i}[/cyan] — {label}{marker}")
        console.print(f"      [dim]media/{example}[/dim]")
    choice = Prompt.ask(
        "Choice",
        choices=[str(i) for i in range(1, len(keys) + 1)],
        default=str(keys.index(DEFAULT_SCHEME) + 1),
    )
    return keys[int(choice) - 1]


def _interactive_paths(console: Console, source: Path | None, dest: Path | None) -> tuple[Path, Path]:
    if source is None:
        source = Path(Prompt.ask("[bold]Source folder[/bold] (media to organize)")).expanduser()
    while not source.exists() or not source.is_dir():
        console.print(f"[red]✗[/red] {source} is not a directory")
        source = Path(Prompt.ask("[bold]Source folder[/bold]")).expanduser()

    if dest is None:
        default_dest = source.parent / f"{source.name}-Organized"
        dest = Path(Prompt.ask("[bold]Destination root[/bold]", default=str(default_dest))).expanduser()

    if dest.resolve() == source.resolve():
        console.print("[red]✗[/red] Destination must differ from source")
        sys.exit(1)
    try:
        dest.resolve().relative_to(source.resolve())
        console.print("[red]✗[/red] Destination must not be inside source")
        sys.exit(1)
    except ValueError:
        pass

    return source.resolve(), dest.resolve()


def _action_menu(console: Console) -> str:
    console.print()
    console.print("[bold]What next?[/bold]")
    console.print("  [cyan]a[/cyan] — apply this plan (copy + verify, then delete originals)")
    console.print("  [cyan]c[/cyan] — copy only, keep originals")
    console.print("  [cyan]t[/cyan] — show full destination tree")
    console.print("  [cyan]s[/cyan] — save manifest and exit")
    console.print("  [cyan]q[/cyan] — quit without doing anything")
    return Prompt.ask("Choice", choices=["a", "c", "t", "s", "q"], default="a")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="organizer",
        description="Organize media files into Year/Month/Camera folders based on metadata.",
    )
    parser.add_argument("source", nargs="?", type=Path, help="Source folder to scan")
    parser.add_argument("-d", "--dest", type=Path, help="Destination root")
    parser.add_argument("-w", "--workers", type=int, default=8, help="Parallel worker threads")
    parser.add_argument("--batch-size", type=int, default=200, help="Metadata batch size")
    parser.add_argument("--manifest", type=Path, help="Path to save/load manifest JSON")
    parser.add_argument("--resume", action="store_true", help="Resume from existing manifest")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation, apply plan")
    parser.add_argument(
        "--scheme", choices=list(SCHEMES.keys()),
        help="Folder scheme (skips interactive prompt). Default: year-month-camera",
    )
    args = parser.parse_args()

    console = Console()
    console.print(Panel.fit(
        "[bold blue]File Organizer[/bold blue]\n"
        "[dim]Sorts media by Year/Month/Camera using EXIF metadata.[/dim]",
        border_style="blue",
    ))

    if args.resume:
        if not args.manifest or not args.manifest.exists():
            console.print("[red]✗[/red] --resume requires existing --manifest path")
            return 1
        manifest = Manifest.load(args.manifest)
        console.print(f"[green]✓[/green] Loaded manifest from {args.manifest}")
        render_summary(console, manifest)
        if not args.yes and not Confirm.ask("Resume applying this plan?", default=True):
            return 0
        succeeded, failed = execute(
            manifest, console, workers=args.workers,
            delete_source=True, manifest_path=args.manifest,
        )
        console.print(f"\n[green]✓[/green] {succeeded} succeeded, [red]{failed} failed[/red]")
        return 0 if failed == 0 else 1

    source, dest = _interactive_paths(console, args.source, args.dest)
    manifest_path = args.manifest or (dest / ".organizer-manifest.json")

    files = _scan_with_progress(console, source)
    if not files:
        console.print("[yellow]No files found. Nothing to do.[/yellow]")
        return 0

    metas = _extract_with_progress(console, files, workers=args.workers, batch_size=args.batch_size)
    scheme = _interactive_scheme(console, args.scheme)
    manifest = build_manifest(source, dest, files, metas, scheme=scheme)

    console.print()
    render_summary(console, manifest)

    while True:
        choice = "a" if args.yes else _action_menu(console)
        if choice == "t":
            render_tree(console, manifest)
            continue
        if choice == "q":
            console.print("[dim]Aborted. No changes made.[/dim]")
            return 0
        if choice == "s":
            manifest.save(manifest_path)
            console.print(f"[green]✓[/green] Manifest saved to {manifest_path}")
            console.print(f"[dim]Resume later with: organizer --resume --manifest {manifest_path}[/dim]")
            return 0
        if choice in ("a", "c"):
            delete_source = (choice == "a")
            if not args.yes:
                msg = (
                    f"Apply plan: copy {len(manifest.entries)} files to {dest}"
                    + (" and DELETE originals after verify" if delete_source else " (originals kept)")
                    + "?"
                )
                if not Confirm.ask(msg, default=False):
                    continue
            manifest.save(manifest_path)
            succeeded, failed = execute(
                manifest, console, workers=args.workers,
                delete_source=delete_source, manifest_path=manifest_path,
            )
            console.print()
            if failed:
                console.print(f"[red]✗[/red] {succeeded} succeeded, {failed} failed")
                console.print(f"[dim]Manifest at {manifest_path} — fix issues and re-run with --resume[/dim]")
                return 1
            console.print(f"[bold green]✓ Done.[/bold green] {succeeded} files organized into {dest}")
            return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
