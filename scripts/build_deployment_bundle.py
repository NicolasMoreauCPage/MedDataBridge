#!/usr/bin/env python3
"""Construit un livrable depuis les sources canoniques du dépôt.

Les répertoires de déploiement ne contiennent plus de copie de ``app/``. Cette
commande crée une archive déterministe des sources courantes et peut télécharger
le wheelhouse correspondant au manifeste runtime.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = (
    "app",
    "config",
    "alembic",
    "alembic.ini",
    "requirements-runtime.txt",
    "requirements-runtime.lock",
    "README.md",
    "init_db.py",
    "docker/entrypoint.sh",
)
IGNORED_PARTS = {"__pycache__", ".pytest_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def _ignore(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in IGNORED_PARTS or Path(name).suffix in IGNORED_SUFFIXES
    }


def stage_sources(destination: Path) -> None:
    for relative in SOURCE_PATHS:
        source = REPOSITORY_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, ignore=_ignore)
        else:
            shutil.copy2(source, target)


def download_wheels(destination: Path) -> None:
    wheelhouse = destination / "wheelhouse"
    wheelhouse.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--requirement",
            str(REPOSITORY_ROOT / "requirements-runtime.lock"),
            "--dest",
            str(wheelhouse),
        ],
        check=True,
    )


def create_archive(output: Path, *, with_wheels: bool) -> Path:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="medbridge-bundle-") as temporary:
        staging = Path(temporary) / "meddata-bridge"
        staging.mkdir()
        stage_sources(staging)
        if with_wheels:
            download_wheels(staging)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging.parent))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--with-wheels", action="store_true")
    args = parser.parse_args()
    print(create_archive(args.output, with_wheels=args.with_wheels))


if __name__ == "__main__":
    main()
