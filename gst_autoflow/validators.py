"""
Shared input validators — used by all 3 modules and the Streamlit app.
Keep all validation logic here so it's easy to audit in one place.
"""
import os
from pathlib import Path

MAX_EXCEL_SIZE_MB = 5
MAX_PDF_SIZE_MB   = 10
ALLOWED_EXCEL_EXT = {".xlsx", ".xls"}
ALLOWED_PDF_EXT   = {".pdf"}


class ValidationError(ValueError):
    """Raised when user-supplied input fails a security/sanity check."""
    pass


def validate_excel(path: str) -> str:
    """Return resolved path or raise ValidationError."""
    p = Path(path).resolve()
    _check_extension(p, ALLOWED_EXCEL_EXT)
    _check_exists(p)
    _check_size(p, MAX_EXCEL_SIZE_MB)
    return str(p)


def validate_pdf(path: str) -> str:
    """Return resolved path or raise ValidationError."""
    p = Path(path).resolve()
    _check_extension(p, ALLOWED_PDF_EXT)
    _check_exists(p)
    _check_size(p, MAX_PDF_SIZE_MB)
    return str(p)


def sanitise_filename(name: str) -> str:
    """
    Strip directory components and non-ASCII chars from a filename.
    Safe to use when echoing back a filename to the UI.
    """
    return Path(name).name.encode("ascii", errors="ignore").decode().strip()


def validate_gstin(gstin: str) -> bool:
    """Return True if string matches the 15-char GSTIN format."""
    import re
    return bool(re.fullmatch(r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]', gstin.upper()))


# ── Internal helpers ──────────────────────────────────────────────────────

def _check_extension(p: Path, allowed: set):
    if p.suffix.lower() not in allowed:
        raise ValidationError(
            f"File type '{p.suffix}' not allowed. Accepted: {', '.join(allowed)}"
        )


def _check_exists(p: Path):
    if not p.is_file():
        raise ValidationError("File not found.")


def _check_size(p: Path, max_mb: float):
    size_mb = p.stat().st_size / (1024 * 1024)
    if size_mb > max_mb:
        raise ValidationError(
            f"File is {size_mb:.1f} MB — exceeds the {max_mb} MB limit."
        )
