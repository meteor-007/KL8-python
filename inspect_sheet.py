import pandas as pd
import os

file_path = r"data\热码统计\20260506-2026116期-热码统计.xlsx"

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
else:
    print(f"File: {file_path}\n")
    
    # Get sheet names
    xls = pd.ExcelFile(file_path)
    print(f"Sheet names: {xls.sheet_names}\n")
    
    # Read first sheet with header=None
    df_raw = pd.read_excel(file_path, sheet_name=0, header=None)
    print(f"Shape: {df_raw.shape}")
    print(f"\nFirst 8 rows (header=None):")
    print(df_raw.head(8).to_string())
    
    # Read with default header
    df_with_header = pd.read_excel(file_path, sheet_name=0)
    print(f"\n\nWith default header - Columns: {list(df_with_header.columns)}")
    print(f"Shape: {df_with_header.shape}")
    print(f"\nFirst 8 rows (default header):")
    print(df_with_header.head(8).to_string())
    
    # Guessed mapping
    print("\n\n=== GUESSED COLUMN MAPPING ===")
    for i, col in enumerate(df_with_header.columns):
        print(f"  [{i}] {col}")
    
    print("\nLikely All/S50/S25/S10 + rank/hits structure:")
    for col_name in df_with_header.columns:
        col_str = str(col_name).lower()
        if any(x in col_str for x in ['all', 's50', 's25', 's10', '排名', '排行', 'rank', '次数', '中奖', 'hits', 'count']):
            print(f"  - {col_name}")
