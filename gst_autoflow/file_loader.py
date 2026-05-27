"""
file_loader.py — Universal file loader for GST AutoFlow.

Handles all the messy real-world formats customers actually send:
  - .xlsx, .xls, .csv, .ods (any common format)
  - Multi-sheet files → let user pick sheet
  - Header not on row 1 → auto-detect or let user set
  - BOM in CSVs, encoding issues → auto-heal
  - Blank/summary rows at top of bank exports → skip

Returns a clean DataFrame + metadata dict for UI to display.
"""
import io
import chardet
import pandas as pd
from pathlib import Path
from .validators import ValidationError

SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".ods"}
MAX_HEADER_SCAN_ROWS = 15   # scan this many rows to find the header


class LoadResult:
    def __init__(self, df, sheet_name=None, header_row=0,
                 encoding=None, file_type=None, warnings=None):
        self.df         = df
        self.sheet_name = sheet_name
        self.header_row = header_row
        self.encoding   = encoding
        self.file_type  = file_type
        self.warnings   = warnings or []


def get_sheet_names(file_bytes: bytes, filename: str) -> list[str]:
    """Return list of sheet names for Excel files. Empty list for CSV."""
    ext = Path(filename).suffix.lower()
    if ext in {".xlsx", ".xls", ".ods"}:
        try:
            xl = pd.ExcelFile(io.BytesIO(file_bytes))
            return xl.sheet_names
        except Exception:
            return []
    return []


def load_file(file_bytes: bytes, filename: str,
              sheet_name: str = None,
              header_row: int = None) -> LoadResult:
    """
    Load any supported file into a clean DataFrame.

    Args:
        file_bytes:  Raw bytes from st.file_uploader
        filename:    Original filename (used for extension detection)
        sheet_name:  For Excel — which sheet to load (None = first sheet)
        header_row:  Which row is the header (None = auto-detect)

    Returns LoadResult with .df and metadata.
    """
    ext      = Path(filename).suffix.lower()
    warnings = []

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValidationError(
            f"File type '{ext}' not supported. "
            f"Accepted: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # ── CSV ────────────────────────────────────────────────────────
    if ext == ".csv":
        encoding, df = _load_csv(file_bytes, warnings)
        if header_row is None:
            header_row, df = _autodetect_header(df, warnings)
        else:
            df = _apply_header_row(df, header_row)
        return LoadResult(df, encoding=encoding, file_type="csv",
                         header_row=header_row, warnings=warnings)

    # ── Excel / ODS ────────────────────────────────────────────────
    xl       = pd.ExcelFile(io.BytesIO(file_bytes))
    sheets   = xl.sheet_names

    if sheet_name is None:
        sheet_name = sheets[0]
        if len(sheets) > 1:
            warnings.append(
                f"File has {len(sheets)} sheets: {', '.join(sheets)}. "
                f"Loaded '{sheet_name}'. Use the sheet selector to change."
            )

    # Load without header first so we can auto-detect
    raw = pd.read_excel(io.BytesIO(file_bytes),
                        sheet_name=sheet_name,
                        header=None, dtype=str)

    if header_row is None:
        header_row, df = _autodetect_header(raw, warnings)
    else:
        df = _apply_header_row(raw, header_row)

    return LoadResult(df, sheet_name=sheet_name, file_type=ext.lstrip("."),
                     header_row=header_row, warnings=warnings)


# ── Internals ──────────────────────────────────────────────────────────

def _load_csv(file_bytes: bytes, warnings: list) -> tuple[str, pd.DataFrame]:
    """Detect encoding and load CSV robustly."""
    detected  = chardet.detect(file_bytes)
    encoding  = detected.get("encoding") or "utf-8"
    # Strip BOM
    if file_bytes[:3] == b'\xef\xbb\xbf':
        file_bytes = file_bytes[3:]
        encoding   = "utf-8"
    try:
        df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding,
                        header=None, dtype=str, on_bad_lines="skip")
    except Exception:
        # Fallback: try latin-1 which accepts all byte values
        df       = pd.read_csv(io.BytesIO(file_bytes), encoding="latin-1",
                               header=None, dtype=str, on_bad_lines="skip")
        encoding = "latin-1"
        warnings.append("File encoding auto-corrected to latin-1.")
    return encoding, df


def _autodetect_header(raw: pd.DataFrame, warnings: list) -> tuple[int, pd.DataFrame]:
    """
    Find the row most likely to be the header.
    Heuristic: the row with the most non-numeric, non-empty string cells.
    Common in Indian bank exports that have 3-6 metadata rows before the table.
    """
    scan_rows = min(MAX_HEADER_SCAN_ROWS, len(raw))
    best_row  = 0
    best_score = -1

    for i in range(scan_rows):
        row    = raw.iloc[i]
        score  = sum(
            1 for v in row
            if isinstance(v, str)
            and v.strip()
            and not _is_numeric(v)
            and len(v.strip()) > 1
        )
        if score > best_score:
            best_score = best_row = i   # intentional: best_row = i

    if best_row > 0:
        warnings.append(
            f"Skipped {best_row} metadata row(s) at top — header detected on row {best_row + 1}. "
            "Use 'Header row' selector to override."
        )

    df = _apply_header_row(raw, best_row)
    return best_row, df


def _apply_header_row(raw: pd.DataFrame, header_row: int) -> pd.DataFrame:
    """Set a specific row as header and drop rows above it."""
    df         = raw.iloc[header_row:].copy()
    df.columns = [str(v).strip() if pd.notna(v) else f"col_{i}"
                  for i, v in enumerate(df.iloc[0])]
    df         = df.iloc[1:].reset_index(drop=True)
    # Drop fully empty rows
    df         = df.dropna(how="all").reset_index(drop=True)
    return df


def _is_numeric(s: str) -> bool:
    try:
        float(s.replace(",", "").replace("₹", "").replace("Rs.", "").strip())
        return True
    except ValueError:
        return False
