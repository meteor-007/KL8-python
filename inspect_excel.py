import pandas as pd

file_path = r'data\热码统计\20260409-2026089期-热码统计.xlsx'

# Read Excel file
xls = pd.ExcelFile(file_path)

# Print sheet names
print('=' * 60)
print('SHEET NAMES:')
print('=' * 60)
for i, sheet in enumerate(xls.sheet_names, 1):
    print(f'{i}. {sheet}')

# Print data for each sheet
for sheet_name in xls.sheet_names:
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    print('\n' + '=' * 60)
    print(f'SHEET: {sheet_name}')
    print('=' * 60)
    print(f'Shape: {df.shape[0]} rows × {df.shape[1]} columns')
    print(f'\nColumns: {list(df.columns)}')
    print(f'\nFirst 8 rows:')
    print(df.head(8).to_string())
