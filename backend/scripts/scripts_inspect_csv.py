from pathlib import Path

import pandas as pd


path = Path(
    r"E:\repository\MikotoRecord\录播完整检查.csv"
)

df = pd.read_csv(path)

print("行数:", len(df))
print("\n字段:")
for column in df.columns:
    print(repr(column))

print("\n前 3 行:")
print(df.head(3).to_string())
