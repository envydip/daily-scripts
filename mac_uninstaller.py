#!/usr/bin/env python3
"""
mac_uninstaller.py — Clean uninstaller for macOS apps.

Usage:
    python3 mac_uninstaller.py <AppName> [--bundle-id <com.example.app>] [--dry-run]

Examples:
    python3 mac_uninstaller.py Motrix
    python3 mac_uninstaller.py Firefox --dry-run
    python3 mac_uninstaller.py Firefox --bundle-id org.mozilla.firefox --dry-run
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


HOME = Path.home()

# All locations macOS apps can leave files
SEARCH_ROOTS = [
    Path("/Applications"),
    HOME / "Applications",
    HOME / "Library" / "Application Support",
    HOME / "Library" / "Caches",
    HOME / "Library" / "Preferences",
    HOME / "Library" / "Logs",
    HOME / "Library" / "Cookies",
    HOME / "Library" / "WebKit",
    HOME / "Library" / "HTTPStorages",
    HOME / "Library" / "Saved Application State",
    HOME / "Library" / "Containers",
    HOME / "Library" / "Group Containers",
    HOME / "Library" / "LaunchAgents",
    Path("/Library") / "LaunchAgents",
    Path("/Library") / "LaunchDaemons",
    Path("/Library") / "Application Support",
    Path("/Library") / "Preferences",
    Path("/private/var/folders"),
]

# Paths that are never touched (user data, other apps' internals)
SKIP_PATHS = [
    HOME / "Downloads",
    HOME / "Documents",
    HOME / "Desktop",
    HOME / "Movies",
    HOME / "Music",
    HOME / "Pictures",
]


def is_inside_other_app(path: Path, keywords: list[str]) -> bool:
    """Return True if path lives inside a .app bundle that doesn't match any keyword."""
    for part in path.parts:
        if part.endswith(".app"):
            app_stem = part[:-4].lower()
            if any(kw.lower() in app_stem for kw in keywords):
                return False  # this .app is the target
            return True  # inside a different app (e.g. VS Code, Ghostty)
    return False


def detect_bundle_id(app_name: str) -> str | None:
    """Use mdls to auto-detect the bundle ID from the installed .app."""
    for app_dir in (Path("/Applications"), HOME / "Applications"):
        app_path = app_dir / f"{app_name}.app"
        if app_path.exists():
            out = subprocess.run(
                ["mdls", "-name", "kMDItemCFBundleIdentifier", str(app_path)],
                capture_output=True,
                text=True,
            )
            for line in out.stdout.splitlines():
                if "=" in line and "(null)" not in line:
                    bundle_id = line.split("=", 1)[1].strip().strip('"')
                    return bundle_id
    return None


def is_system_temp_artifact(path: Path) -> bool:
    """Skip Safari/system import temp dirs that aren't the app's own data."""
    skip_containers = [
        HOME / "Library" / "Containers" / "com.apple.Safari.BrowserDataImportingService",
    ]
    return any(str(path).startswith(str(s)) for s in skip_containers)


def find_with_fd(keyword: str, all_keywords: list[str]) -> list[Path]:
    results: list[Path] = []
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        try:
            out = subprocess.run(
                ["fd", "-i", "-u", keyword, str(root)],
                capture_output=True,
                text=True,
            )
            for line in out.stdout.splitlines():
                p = Path(line.strip())
                if any(str(p).startswith(str(skip)) for skip in SKIP_PATHS):
                    continue
                if is_inside_other_app(p, all_keywords):
                    continue
                if is_system_temp_artifact(p):
                    continue
                results.append(p)
        except FileNotFoundError:
            print("Error: 'fd' is not installed. Install via: brew install fd")
            sys.exit(1)
    return results


def deduplicate(paths: list[Path]) -> list[Path]:
    """Remove paths that are children of other paths in the list."""
    sorted_paths = sorted(set(paths), key=lambda p: len(p.parts))
    deduped: list[Path] = []
    for p in sorted_paths:
        if not any(str(p).startswith(str(kept) + os.sep) for kept in deduped):
            deduped.append(p)
    return deduped


def remove(path: Path) -> tuple[bool, str]:
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True, ""
    except PermissionError:
        return False, "Permission denied (try sudo)"
    except Exception as e:
        return False, str(e)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean uninstaller for macOS apps.")
    parser.add_argument("app", help="App name to search for (e.g. Motrix)")
    parser.add_argument("--bundle-id", help="Bundle ID prefix (e.g. app.motrix.native)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without deleting")
    args = parser.parse_args()

    keywords = [args.app]

    bundle_id = args.bundle_id or detect_bundle_id(args.app)
    if bundle_id:
        print(f"Bundle ID detected: {bundle_id}")
        # Search by full bundle ID only — avoid broad prefixes that match other apps
        if bundle_id not in keywords:
            keywords.append(bundle_id)

    print(f"\nSearching for '{args.app}' files...\n")

    found: list[Path] = []
    for kw in keywords:
        found.extend(find_with_fd(kw, keywords))

    found = deduplicate(found)

    if not found:
        print("No files found. App may already be clean.")
        return

    print(f"Found {len(found)} item(s):\n")
    for p in found:
        tag = "[DIR] " if p.is_dir() else "[FILE]"
        print(f"  {tag} {p}")

    if args.dry_run:
        print("\n[Dry run] No files were deleted.")
        return

    print()
    confirm = input("Delete all of the above? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    print()
    failed: list[tuple[Path, str]] = []
    for p in found:
        if not p.exists():
            continue
        ok, err = remove(p)
        if ok:
            print(f"  Removed: {p}")
        else:
            print(f"  FAILED:  {p} ({err})")
            failed.append((p, err))

    print()
    if failed:
        print(f"Done with {len(failed)} error(s).")
    else:
        print("Done. App fully removed.")


if __name__ == "__main__":
    main()
