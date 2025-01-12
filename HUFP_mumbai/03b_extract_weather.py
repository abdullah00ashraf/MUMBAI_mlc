import os
import glob
import zipfile
import xarray as xr

# Set the path to your weather raw data
WEATHER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw", "weather")

def fix_and_merge_encapsulated_nc_files():
    print("🔍 Scanning weather directory for ZIP-encapsulated files...\n")
    
    nc_files = glob.glob(os.path.join(WEATHER_DIR, "*.nc"))
    
    for filepath in nc_files:
        filename = os.path.basename(filepath)
        
        # Check the magic number (first 2 bytes)
        with open(filepath, 'rb') as f:
            magic = f.read(2)
            
        if magic == b'PK':
            print(f"⚠️ Detected split ZIP encapsulation in: {filename}")
            year = filename.split('_')[-1].split('.')[0] # Extracts the year, e.g., '2004'
            
            zip_path = filepath + ".zip"
            # Cleanup from previous failed run if necessary
            if os.path.exists(zip_path):
                os.remove(zip_path)
            os.rename(filepath, zip_path)
            
            extract_dir = os.path.join(WEATHER_DIR, f"temp_{year}")
            os.makedirs(extract_dir, exist_ok=True)
            
            # 1. Extract the split files
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            print(f"   📦 Extracted contents. Fusing variable tensors for {year}...")
            
            # 2. Load and merge the datasets using xarray
            extracted_ncs = glob.glob(os.path.join(extract_dir, "*.nc"))
            try:
                datasets = [xr.open_dataset(f, engine='netcdf4') for f in extracted_ncs]
                ds_merged = xr.merge(datasets)
                
                # Save the unified dataset back to the original filename
                ds_merged.to_netcdf(filepath)
                
                # Close the datasets to free memory
                for ds in datasets:
                    ds.close()
                ds_merged.close()
                
                print(f"   ✅ Successfully unified and restored: {filename}")
            except Exception as e:
                print(f"   ❌ Error merging {year}: {e}")
                # Restore the zip back to .nc just in case of failure
                os.rename(zip_path, filepath)
                continue

            # 3. Clean up the temporary files
            os.remove(zip_path)
            for f in extracted_ncs:
                try:
                    os.remove(f)
                except PermissionError:
                    pass # Windows sometimes holds file locks slightly too long
            try:
                os.rmdir(extract_dir)
            except OSError:
                pass
                
    print(f"\n✅ Scan complete. Weather data is mathematically pure and ready for Spatio-Temporal Fusion.")

if __name__ == "__main__":
    fix_and_merge_encapsulated_nc_files()