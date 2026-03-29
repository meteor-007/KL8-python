import pandas as pd
import json
import os
import sys

# Set encoding for output
if sys.stdout.encoding != 'utf-8':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

file_path = r'D:\Dpanqianyi\Python-Project\KL8-点位-CODE\src\data-sum\每期专家关注号命中追踪.xlsx'

def analyze_excel():
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    try:
        # Load the Excel file to list sheets
        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names
        print(f"Sheet names: {sheet_names}")

        # Target sheet
        target_sheet = "AI模型推演报告板"
        if target_sheet not in sheet_names:
            print(f"Target sheet '{target_sheet}' not found. Available: {sheet_names}")
            # Try a fuzzy match
            for s in sheet_names:
                if "AI模型" in s or "报告" in s:
                    target_sheet = s
                    print(f"Closest match found: {target_sheet}")
                    break
            else:
                return

        # Load the specific sheet
        df = pd.read_excel(file_path, sheet_name=target_sheet)
        
        # Display the first few rows to understand structure
        print("First 20 rows of the sheet:")
        print(df.head(20).to_string())
        
        # Check columns
        print("\nColumns found:")
        print(df.columns.tolist())
        
    except Exception as e:
        print(f"Error reading Excel: {e}")

if __name__ == "__main__":
    analyze_excel()
