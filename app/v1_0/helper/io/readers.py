import io, csv
from typing import List, Dict, Tuple, Optional
import pandas as pd

def read_csv(content: bytes, delimiter: Optional[str] = None) -> Tuple[List[Dict], Dict]:
    text = content.decode("utf-8-sig", errors="ignore")
    if delimiter is None:
        try:
            sniff = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
            sep = sniff.delimiter
        except Exception:
            sep = ","
    else:
        sep = "\t" if delimiter == "tab" else delimiter

    df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() if c is not None else "" for c in df.columns]
    rows = df.to_dict(orient="records")
    return rows, {"delimiter": sep, "encoding": "utf-8-sig", "columns": list(df.columns)}

def read_xlsx(content: bytes, sheet: Optional[str] = None, header_row: int = 1) -> Tuple[List[Dict], Dict]:
    bio = io.BytesIO(content)
    with pd.ExcelFile(bio, engine="openpyxl") as xl:
        target = sheet if sheet in xl.sheet_names else xl.sheet_names[0]
        df = xl.parse(sheet_name=target, header=header_row - 1, dtype=str)
    df = df.fillna("")
    df.columns = [str(c).strip() if c is not None else "" for c in df.columns]
    rows = df.to_dict(orient="records")
    return rows, {"sheet": target, "header_row": header_row, "columns": list(df.columns)}