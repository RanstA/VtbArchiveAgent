import argparse
from pathlib import Path

import pandas as pd


DEFAULT_PATH = Path(
    r"E:\repository\MikotoRecord\录播完整检查.csv"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect raw columns and rows in an archive CSV file.")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()

    df = pd.read_csv(args.path)

    print("行数:", len(df))
    print("\n字段:")
    for column in df.columns:
        print(repr(column))

    print("\n前 3 行:")
    print(df.head(3).to_string())


if __name__ == "__main__":
    main()
