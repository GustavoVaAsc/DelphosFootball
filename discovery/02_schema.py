"""02 — Schema: per-column dtype, null count and null rate for every file.

Memory approach: the three big files are streamed in 250k-row chunks and null
counts are accumulated per column; small files are read in full. dtypes are
inferred by pandas per chunk; if a column's inferred dtype varies across
chunks it is reported as 'mixed'.
"""
import pandas as pd

from common import DATA_DIR, FILES, BIG_FILES, CHUNKSIZE, save


def profile_file(path):
    big = path.name in BIG_FILES
    nulls = {}
    dtypes = {}
    n_rows = 0
    cols = list(pd.read_csv(path, nrows=0).columns)
    for c in cols:
        nulls[c] = 0
        dtypes[c] = set()
    if big:
        reader = pd.read_csv(path, chunksize=CHUNKSIZE)
        for chunk in reader:
            n_rows += len(chunk)
            for c in chunk.columns:
                nulls[c] += int(chunk[c].isna().sum())
                dtypes[c].add(str(chunk[c].dtype))
    else:
        df = pd.read_csv(path)
        n_rows = len(df)
        for c in df.columns:
            nulls[c] = int(df[c].isna().sum())
            dtypes[c].add(str(df[c].dtype))
    columns = []
    for c in cols:
        dt = sorted(dtypes[c])
        columns.append(
            {
                "name": c,
                "dtype": dt[0] if len(dt) == 1 else f"mixed({','.join(dt)})",
                "nulls": nulls[c],
                "null_rate": round(nulls[c] / n_rows, 6) if n_rows else None,
                "flag_gt20pct_null": nulls[c] / n_rows > 0.20 if n_rows else False,
            }
        )
    return {"n_rows": n_rows, "columns": columns}


def main():
    out = {}
    for fname in FILES:
        out[fname] = profile_file(DATA_DIR / fname)
        flagged = [c["name"] for c in out[fname]["columns"] if c["flag_gt20pct_null"]]
        print(fname, out[fname]["n_rows"], "rows; >20% null:", flagged)
    save("02_schema", out)


if __name__ == "__main__":
    main()
