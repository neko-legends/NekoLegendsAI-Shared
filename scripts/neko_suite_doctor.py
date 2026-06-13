#!/usr/bin/env python3
"""neko-suite-doctor — cross-repo invariant checker for the Neko Legends suite.

Lives in NekoLegendsAI-Shared because that repo is the source of truth for
suite-wide conventions. It validates the two invariants that are easy to break
by hand and have already caused near-misses:

  1. VENDORED MODULE DRIFT — every app copies (vendors) `neko_store.rs` from this
     repo. Nothing stops an app's copy from going stale after a canonical fix.
     This checks each app's vendored copy against the canonical one.

  2. AGENT API PORT COLLISIONS — each app exposes a local HTTP Agent API on a
     unique port. The authoritative list is `default_agent_api_entries()` in the
     Control Center's Rust source. This parses it, fails on any duplicate port,
     and (with --write-registry) regenerates AGENT_API_PORTS.md so the human-
     readable doc can never silently drift from the code.

Layout assumption: all suite repos are checked out as siblings under one folder
(e.g. D:\\forPublic\\). The script locates that root relative to its own path.

Exit code 0 = all good. Non-zero = at least one problem (CI / pre-release gate).

Usage:
    python neko_suite_doctor.py                 # check everything
    python neko_suite_doctor.py --write-registry  # also regenerate AGENT_API_PORTS.md
    python neko_suite_doctor.py --quiet         # only print problems
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

# This file is <suite_root>/NekoLegendsAI-Shared/scripts/neko_suite_doctor.py
SHARED_REPO = Path(__file__).resolve().parent.parent
SUITE_ROOT = SHARED_REPO.parent

CANONICAL_RUST = SHARED_REPO / "rust" / "neko_store.rs"
CONTROL_CENTER_MAIN = SUITE_ROOT / "NekoLegendsControlCenter" / "src-tauri" / "src" / "main.rs"
PORT_REGISTRY_DOC = SUITE_ROOT / "AGENT_API_PORTS.md"

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"


def _supports_color() -> bool:
    return sys.stdout.isatty()


def c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}" if _supports_color() else text


def normalized_hash(path: Path) -> str:
    """Hash file bytes with line endings normalized (CRLF/LF agnostic).

    Git's autocrlf can rewrite line endings in working trees, which would
    otherwise produce false drift positives.
    """
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def find_vendored_copies() -> list[Path]:
    """Every <suite_root>/<app>/src-tauri/src/neko_store.rs except the canonical."""
    copies: list[Path] = []
    for app_dir in sorted(SUITE_ROOT.iterdir()):
        if not app_dir.is_dir():
            continue
        candidate = app_dir / "src-tauri" / "src" / "neko_store.rs"
        if candidate.exists():
            copies.append(candidate)
    return copies


def check_drift(quiet: bool) -> list[str]:
    """Return a list of problem strings (empty = OK)."""
    problems: list[str] = []
    if not CANONICAL_RUST.exists():
        return [f"Canonical module missing: {CANONICAL_RUST}"]

    canonical = normalized_hash(CANONICAL_RUST)
    copies = find_vendored_copies()

    if not quiet:
        print(c("● Vendored module drift", YELLOW))
        print(f"  canonical: {DIM if _supports_color() else ''}{CANONICAL_RUST}{RESET if _supports_color() else ''}")

    if not copies:
        if not quiet:
            print("  (no vendored copies found)")
        return problems

    for copy in copies:
        app = copy.relative_to(SUITE_ROOT).parts[0]
        if normalized_hash(copy) == canonical:
            if not quiet:
                print(f"  {c('✓', GREEN)} {app}")
        else:
            problems.append(
                f"DRIFT: {app} vendored neko_store.rs differs from canonical.\n"
                f"       fix: cp '{CANONICAL_RUST}' '{copy}'"
            )
            if not quiet:
                print(f"  {c('✗', RED)} {app}  (out of sync)")
    return problems


def parse_agent_ports() -> list[tuple[str, str, int]]:
    """Parse default_agent_api_entry("id", "name", PORT, ...) from the Control Center.

    Returns list of (app_id, app_name, port).
    """
    if not CONTROL_CENTER_MAIN.exists():
        return []
    text = CONTROL_CENTER_MAIN.read_text(encoding="utf-8", errors="replace")
    # default_agent_api_entry(
    #     "id",
    #     "Name",
    #     17334,
    pattern = re.compile(
        r'default_agent_api_entry\(\s*'
        r'"([^"]+)"\s*,\s*'
        r'"([^"]+)"\s*,\s*'
        r'(\d+)\s*,',
        re.MULTILINE,
    )
    return [(m.group(1), m.group(2), int(m.group(3))) for m in pattern.finditer(text)]


def check_ports(quiet: bool) -> list[str]:
    problems: list[str] = []
    entries = parse_agent_ports()

    if not quiet:
        print(c("\n● Agent API port collisions", YELLOW))
        print(f"  source: {DIM if _supports_color() else ''}{CONTROL_CENTER_MAIN}{RESET if _supports_color() else ''}")

    if not entries:
        problems.append(f"Could not parse any agent ports from {CONTROL_CENTER_MAIN}")
        return problems

    by_port: dict[int, list[str]] = {}
    for app_id, _name, port in entries:
        by_port.setdefault(port, []).append(app_id)

    for app_id, _name, port in sorted(entries, key=lambda e: e[2]):
        dupes = by_port[port]
        if len(dupes) > 1:
            if not quiet:
                print(f"  {c('✗', RED)} {port}  {app_id}  (collides with {', '.join(x for x in dupes if x != app_id)})")
        elif not quiet:
            print(f"  {c('✓', GREEN)} {port}  {app_id}")

    for port, apps in by_port.items():
        if len(apps) > 1:
            problems.append(f"PORT COLLISION: {port} used by {', '.join(apps)}")
    return problems


def write_registry() -> None:
    """Regenerate AGENT_API_PORTS.md from the Control Center entries."""
    entries = sorted(parse_agent_ports(), key=lambda e: e[2])
    if not entries:
        print(c("Cannot regenerate registry: no entries parsed.", RED))
        return

    lines = [
        "# Agent API Port Registry",
        "",
        "> **Auto-generated** by `NekoLegendsAI-Shared/scripts/neko_suite_doctor.py`",
        "> from `NekoLegendsControlCenter/src-tauri/src/main.rs`"
        " (`default_agent_api_entries`).",
        "> Do not edit by hand — change the Rust source, then run"
        " `neko_suite_doctor.py --write-registry`.",
        "",
        "Agent APIs are off by default, bind to the listed address, and are"
        " configurable per app from its settings.",
        "",
        "| App | Default port | Bind address |",
        "| --- | ---: | --- |",
    ]
    for app_id, name, port in entries:
        bind = "0.0.0.0" if app_id == "venice-media-local" else "127.0.0.1"
        lines.append(f"| {name} | {port} | {bind} |")
    lines.append("")
    PORT_REGISTRY_DOC.write_text("\n".join(lines), encoding="utf-8")
    print(c(f"Wrote {PORT_REGISTRY_DOC}", GREEN))


def main() -> int:
    parser = argparse.ArgumentParser(description="Neko Legends suite invariant checker.")
    parser.add_argument("--write-registry", action="store_true",
                        help="Regenerate AGENT_API_PORTS.md from the Control Center source.")
    parser.add_argument("--quiet", action="store_true", help="Only print problems.")
    args = parser.parse_args()

    if not args.quiet:
        print(c(f"neko-suite-doctor — suite root: {SUITE_ROOT}", DIM))
        print()

    problems: list[str] = []
    problems += check_drift(args.quiet)
    problems += check_ports(args.quiet)

    if args.write_registry:
        print()
        write_registry()

    print()
    if problems:
        print(c(f"✗ {len(problems)} problem(s) found:", RED))
        for p in problems:
            print(c(f"  - {p}", RED))
        return 1

    print(c("✓ All suite invariants OK.", GREEN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
