#!/usr/bin/env python3
"""
Script de gestion des versions pour MedData Bridge.

Utilisation:
    python version_manager.py bump [major|minor|patch|prerelease]
    python version_manager.py set <version>
    python version_manager.py current
"""

import sys
import re
from pathlib import Path
from typing import Tuple, Optional


def parse_version(version: str) -> Tuple[int, int, int, Optional[str]]:
    """Parse une version semver en composants."""
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$', version)
    if not match:
        raise ValueError(f"Version invalide: {version}")

    major, minor, patch, prerelease = match.groups()
    return int(major), int(minor), int(patch), prerelease


def format_version(major: int, minor: int, patch: int, prerelease: Optional[str] = None) -> str:
    """Formate les composants en version semver."""
    version = f"{major}.{minor}.{patch}"
    if prerelease:
        version += f"-{prerelease}"
    return version


def bump_version(current_version: str, bump_type: str) -> str:
    """Incrémente la version selon le type demandé."""
    major, minor, patch, prerelease = parse_version(current_version)

    if bump_type == "major":
        return format_version(major + 1, 0, 0, prerelease)
    elif bump_type == "minor":
        return format_version(major, minor + 1, 0, prerelease)
    elif bump_type == "patch":
        return format_version(major, minor, patch + 1, prerelease)
    elif bump_type == "prerelease":
        if prerelease:
            # Incrémente le numéro de prérelease
            pre_parts = prerelease.split(".")
            if len(pre_parts) == 2 and pre_parts[1].isdigit():
                pre_num = int(pre_parts[1]) + 1
                return format_version(major, minor, patch, f"{pre_parts[0]}.{pre_num}")
            else:
                return format_version(major, minor, patch, f"{prerelease}.1")
        else:
            return format_version(major, minor, patch, "alpha.1")
    else:
        raise ValueError(f"Type de bump invalide: {bump_type}")


def update_version_file(new_version: str) -> None:
    """Met à jour le fichier VERSION."""
    version_file = Path(__file__).parent / "VERSION"
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(new_version + "\n")
    print(f"✅ VERSION mis à jour: {new_version}")


def update_pyproject_toml(new_version: str) -> None:
    """Met à jour la version dans pyproject.toml."""
    pyproject_file = Path(__file__).parent / "pyproject.toml"
    content = pyproject_file.read_text(encoding="utf-8")
    updated_content = re.sub(
        r'^version = ".*?"$',
        f'version = "{new_version}"',
        content,
        flags=re.MULTILINE
    )
    pyproject_file.write_text(updated_content, encoding="utf-8")
    print(f"✅ pyproject.toml mis à jour: {new_version}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "current":
        from app.version import get_version
        print(get_version())
        sys.exit(0)

    # Lire la version actuelle
    version_file = Path(__file__).parent / "VERSION"
    if not version_file.exists():
        print("❌ Fichier VERSION introuvable")
        sys.exit(1)

    current_version = version_file.read_text(encoding="utf-8").strip()

    if command == "bump":
        if len(sys.argv) < 3:
            print("❌ Spécifiez le type de bump: major, minor, patch, ou prerelease")
            sys.exit(1)
        bump_type = sys.argv[2]
        new_version = bump_version(current_version, bump_type)
    elif command == "set":
        if len(sys.argv) < 3:
            print("❌ Spécifiez la nouvelle version")
            sys.exit(1)
        new_version = sys.argv[2]
        # Valider la version
        parse_version(new_version)
    else:
        print(f"❌ Commande inconnue: {command}")
        print(__doc__)
        sys.exit(1)

    print(f"Version actuelle: {current_version}")
    print(f"Nouvelle version: {new_version}")

    # Confirmer
    response = input("Confirmer la mise à jour ? (y/N): ")
    if response.lower() not in ['y', 'yes', 'oui']:
        print("❌ Annulé")
        sys.exit(0)

    # Mettre à jour les fichiers
    update_version_file(new_version)
    update_pyproject_toml(new_version)

    print("✅ Version mise à jour avec succès")
    print(f"   Pensez à créer un commit et un tag: git tag -a v{new_version}")


if __name__ == "__main__":
    main()