"""01 — File inventory: row/col counts, sizes, PK-candidate uniqueness, date ranges.

Memory approach: reads only date columns + PK-candidate columns via usecols;
the three big files (game_lineups, appearances, game_events) are streamed in
chunks; small files are read in full (they are a few MB of selected columns).
"""
import pandas as pd

from common import DATA_DIR, FILES, PK_CANDIDATES, BIG_FILES, CHUNKSIZE, save


def date_cols_of(path):
    cols = list(pd.read_csv(path, nrows=0).columns)
    return [c for c in cols if "date" in c.lower()]


def scan(path, date_cols, pk_cols):
    usecols = sorted(set(date_cols) | set(pk_cols))
    n_rows = 0
    dmin, dmax = {}, {}
    if str(path.name) in BIG_FILES:
        reader = pd.read_csv(path, usecols=usecols, chunksize=CHUNKSIZE, dtype=str)
        frames = []
        for chunk in reader:
            n_rows += len(chunk)
            frames.append(chunk)
        df = pd.concat(frames, ignore_index=True)
    else:
        df = pd.read_csv(path, usecols=usecols, dtype=str)
        n_rows = len(df)
    for c in date_cols:
        s = pd.to_datetime(df[c], errors="coerce")
        dmin[c] = str(s.min().date()) if s.notna().any() else None
        dmax[c] = str(s.max().date()) if s.notna().any() else None
    pk = None
    if pk_cols:
        n_dup = int(df.duplicated(subset=list(pk_cols)).sum())
        pk = {
            "columns": list(pk_cols),
            "n_unique_keys": int(df.drop_duplicates(subset=list(pk_cols)).shape[0]),
            "n_duplicate_rows": n_dup,
            "is_unique": n_dup == 0,
        }
    return n_rows, dmin, dmax, pk


def main():
    out = {}
    for fname in FILES:
        path = DATA_DIR / fname
        date_cols = date_cols_of(path)
        pk_cols = PK_CANDIDATES[fname]
        n_rows, dmin, dmax, pk = scan(path, date_cols, pk_cols)
        ncols = len(pd.read_csv(path, nrows=0).columns)
        out[fname] = {
            "size_bytes": path.stat().st_size,
            "size_mb": round(path.stat().st_size / 1_048_576, 1),
            "n_rows": n_rows,
            "n_cols": ncols,
            "date_columns": date_cols,
            "date_min": dmin,
            "date_max": dmax,
            "pk_candidate": pk,
        }
        print(fname, n_rows, "rows,", ncols, "cols, pk:", pk and pk["is_unique"])
    save("01_inventory", out)


if __name__ == "__main__":
    main()
