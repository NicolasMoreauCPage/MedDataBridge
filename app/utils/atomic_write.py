from pathlib import Path
import logging
import os
import time
import random

logger = logging.getLogger(__name__)


def _ensure_dir(d: Path):
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.debug("Optional operation skipped", exc_info=exc)
def write_atomic_text(target_dir: Path, basename: str, content: str, extension: str = ".hl7") -> Path:
    """Write content to target_dir/basename_<timestamp>-<rand><extension> atomically.

    Writes to a .tmp file then os.replace() to move to final filename.
    Returns the Path to the final file.
    """
    if not isinstance(target_dir, Path):
        target_dir = Path(target_dir)
    _ensure_dir(target_dir)
    ts = int(time.time())
    rand = random.randint(1000, 9999)
    filename = f"{basename}_{ts}-{rand}{extension}"
    final_path = target_dir / filename
    tmp_path = final_path.with_suffix(final_path.suffix + '.tmp')

    # Write to tmp file, flush and fsync to reduce risk on crash
    with tmp_path.open('w', encoding='utf-8') as fh:
        fh.write(content)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except Exception as exc:
            # not fatal on some platforms
            logger.debug("File fsync unsupported", exc_info=exc)

    # Atomic replace
    try:
        os.replace(str(tmp_path), str(final_path))
    except Exception:
        # fallback: try rename
        tmp_path.replace(final_path)

    return final_path


def write_atomic_text_file(final_path: Path, content: str) -> Path:
    """Écrit atomiquement un nom de fichier explicitement choisi.

    Contrairement à :func:`write_atomic_text`, cette variante ne génère ni
    suffixe ni extension : elle est destinée aux partenaires qui imposent un
    nom de dépôt précis. ``os.replace`` garde la publication atomique du
    fichier, y compris lors du remplacement volontaire d'un dépôt précédent.
    """
    final_path = Path(final_path)
    _ensure_dir(final_path.parent)
    tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        fh.write(content)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except Exception as exc:
            logger.debug("Optional operation skipped", exc_info=exc)
    os.replace(str(tmp_path), str(final_path))
    return final_path
