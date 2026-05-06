from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from .planner import Manifest


def _human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.1f} {u}"
        f /= 1024
    return f"{n} B"


def stats(manifest: Manifest) -> dict:
    counts: dict[str, int] = defaultdict(int)
    sizes: dict[str, int] = defaultdict(int)
    cameras: dict[str, int] = defaultdict(int)
    years: dict[str, int] = defaultdict(int)
    unknown_date = 0
    unknown_camera = 0

    for e in manifest.entries:
        counts[e.kind] += 1
        sizes[e.kind] += e.size
        if e.kind == "media":
            cameras[e.camera or "Unknown-Camera"] += 1
            if e.taken:
                years[e.taken[:4]] += 1
            else:
                unknown_date += 1
            if not e.camera or e.camera == "Unknown-Camera":
                unknown_camera += 1

    return {
        "counts": dict(counts),
        "sizes": dict(sizes),
        "cameras": dict(cameras),
        "years": dict(years),
        "unknown_date": unknown_date,
        "unknown_camera": unknown_camera,
        "total_files": len(manifest.entries),
        "total_size": sum(sizes.values()),
    }


def render_summary(console: Console, manifest: Manifest) -> None:
    s = stats(manifest)

    table = Table(title="Plan Summary", show_header=True, header_style="bold cyan")
    table.add_column("Category")
    table.add_column("Files", justify="right")
    table.add_column("Size", justify="right")
    for kind in ("media", "sidecar", "non-media"):
        c = s["counts"].get(kind, 0)
        sz = s["sizes"].get(kind, 0)
        table.add_row(kind, str(c), _human_size(sz))
    table.add_row("[bold]TOTAL[/bold]", f"[bold]{s['total_files']}[/bold]", f"[bold]{_human_size(s['total_size'])}[/bold]")
    console.print(table)

    if s["cameras"]:
        cam_table = Table(title="Cameras", show_header=True, header_style="bold magenta")
        cam_table.add_column("Camera")
        cam_table.add_column("Files", justify="right")
        for cam, n in sorted(s["cameras"].items(), key=lambda x: -x[1]):
            cam_table.add_row(cam, str(n))
        console.print(cam_table)

    if s["years"]:
        yr_table = Table(title="Years", show_header=True, header_style="bold green")
        yr_table.add_column("Year")
        yr_table.add_column("Files", justify="right")
        for yr, n in sorted(s["years"].items()):
            yr_table.add_row(yr, str(n))
        console.print(yr_table)

    warnings = []
    if s["unknown_date"]:
        warnings.append(f"{s['unknown_date']} media files have no date metadata (placed in Unknown-Date)")
    if s["unknown_camera"]:
        warnings.append(f"{s['unknown_camera']} media files have no camera metadata (placed in Unknown-Camera)")
    if warnings:
        console.print()
        for w in warnings:
            console.print(f"[yellow]![/yellow] {w}")


def render_tree(console: Console, manifest: Manifest, max_files_per_dir: int = 5) -> None:
    dest_root = Path(manifest.dest_root)
    by_dir: dict[Path, list[str]] = defaultdict(list)
    for e in manifest.entries:
        dest = Path(e.destination)
        by_dir[dest.parent].append(dest.name)

    tree = Tree(f"[bold blue]{dest_root}[/bold blue]")

    def add_dir(parent_node: Tree, dir_path: Path) -> Tree:
        rel = dir_path.relative_to(dest_root)
        node = parent_node
        for part in rel.parts:
            existing = next((c for c in node.children if getattr(c, "_label_text", None) == part), None)
            if existing is None:
                child = node.add(f"[cyan]{part}/[/cyan]")
                child._label_text = part  # type: ignore[attr-defined]
                node = child
            else:
                node = existing
        return node

    for dir_path in sorted(by_dir.keys()):
        node = add_dir(tree, dir_path)
        files = sorted(by_dir[dir_path])
        for name in files[:max_files_per_dir]:
            node.add(f"[white]{name}[/white]")
        if len(files) > max_files_per_dir:
            node.add(f"[dim]... and {len(files) - max_files_per_dir} more[/dim]")

    console.print(tree)
