from pathlib import Path
import pandas as pd


def inspect_excel(path: str | Path) -> None:
    path = Path(path)
    book = pd.ExcelFile(path)
    print(f"\n=== {path} ===")
    print("sheets:", book.sheet_names)
    for sheet in book.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        print(f"[{sheet}] shape={df.shape}")
        print(df.head())
        print(df.dtypes)
        print("missing:")
        print(df.isna().sum())


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2] / "00_problem" / "attachments"
    for name in ["附件1.xlsx", "附件2.xlsx", "附件3.xlsx", "附件4.xlsx", "result_template.xlsx"]:
        p = root / name
        if p.exists():
            inspect_excel(p)
