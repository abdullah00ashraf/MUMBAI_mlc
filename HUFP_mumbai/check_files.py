import os

file_to_check = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw", "weather", "mumbai_monsoon_era5_2004.nc")

if os.path.exists(file_to_check):
    size = os.path.getsize(file_to_check)
    print(f"File Size: {size / 1024:.2f} KB")
    
    with open(file_to_check, 'rb') as f:
        header = f.read(100)
        print(f"File Header (First 100 bytes): {header}")
else:
    print("File not found.")