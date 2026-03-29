import os

def refactor_file(filepath):
    if not os.path.exists(filepath):
        print(f"Skipping {filepath}")
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    current_numbers = []
    
    for line in lines:
        line = line.strip()
        if '→' in line:
            parts = line.split('→')
            nums = parts[1].strip().split()
            current_numbers.append(nums)
        else:
            # If line is empty or doesn't have →, but we have numbers, we should probably keep counting?
            # Looking at the historical files, empty lines like line 5 are spacers.
            current_numbers.append([])
            
    # Now group into 4-row matrices
    for i in range(0, len(current_numbers), 4):
        matrix_id = (i // 4) + 1
        new_lines.append(f"矩阵{matrix_id}：")
        for j in range(4):
            if i + j < len(current_numbers):
                nums = current_numbers[i+j]
                m1 = nums[:4]
                m2 = nums[4:8]
                # Pad with empty if needed? No, the user's sample doesn't always pad with 4 spaces.
                # But it uses "|" as separator.
                row_str = " ".join(m1) + " | " + " ".join(m2)
                new_lines.append(row_str.strip())
        new_lines.append("") # Spacer between matrices

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(new_lines))
    print(f"Refactored {filepath}")

base_path = r"D:\Dpanqianyi\Python-Project\KL8-点位-CODE\src\data-sum"
dates = ["20260319", "20260320", "20260321", "20260322", "20260323", "20260324"]

for date in dates:
    fp = os.path.join(base_path, date, f"{date}-data1.txt")
    refactor_file(fp)
