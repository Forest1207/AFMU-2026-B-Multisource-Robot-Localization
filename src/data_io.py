from pathlib import Path
import pandas as pd


def read_excel(path: str | Path, **kwargs):
    """Read an Excel workbook using pandas with a Path-friendly interface."""
    return pd.read_excel(Path(path), **kwargs)
