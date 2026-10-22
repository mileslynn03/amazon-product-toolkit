"""Build a standalone source ZIP from an explicit public-source allowlist."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parent
ROOT_FILES = (
    "project.json", "README.md", "README.zh-CN.md", "README.en.md", "LICENSE", ".gitignore",
    "requirements.txt", "requirements-dev.txt", "start_windows.bat", "start_macos.command",
    "launcher.py", "server.py", "_runtime.py", "build_release.py", "marketplaces.py",
    "task_manager.py", "capture.py", "results.py", "translation.py", "exporter.py",
)
SOURCE_DIRECTORIES = {"scraper": {".py"}, "static": {".html", ".css", ".js", ".svg"},
                      "tests": {".py", ".json", ".html"}, "docs": {".md"}}


def source_files(root):
    files = [root / name for name in ROOT_FILES]
    for name, extensions in SOURCE_DIRECTORIES.items():
        folder = root / name
        if folder.is_symlink():
            raise ValueError(f"Source directory must not be a link: {name}")
        for path in folder.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"Source path must not be a link: {path}")
            if path.is_file() and path.suffix in extensions and "__pycache__" not in path.parts:
                files.append(path)
    for path in files:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Invalid source file: {path}")
    return sorted(files)


def build(root=ROOT, output_dir=None):
    root = Path(root).resolve()
    identity = json.loads((root / "project.json").read_text(encoding="utf-8"))
    if not re.fullmatch(r"[a-z0-9-]+", identity["id"]) or not re.fullmatch(r"\d+\.\d+\.\d+", identity["version"]):
        raise ValueError("Invalid project id or source version")
    prefix = f"{identity['id']}-{identity['version']}"
    output_dir = Path(output_dir) if output_dir is not None else root / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"{prefix}-source.zip"
    files = source_files(root)
    manifest = {"project": identity, "files": {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in files}}
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for path in files:
            info = ZipInfo.from_file(path, f"{prefix}/{path.relative_to(root).as_posix()}")
            info.create_system = 3
            mode = 0o755 if path.suffix == ".command" else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            bundle.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED)
        bundle.writestr(f"{prefix}/RELEASE_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{checksum}  {archive.name}\n", encoding="ascii")
    return archive


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the Amazon Review Scraper GUI standalone source ZIP")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    print(build(output_dir=args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
