"""
PROJECT SALSETTE: THE KONKAN-AEGIS PROTOCOL
MODULE: PURE PYTHON TRANSPORT MATRIX FORGE (AZTEC)
PAYLOAD: ZERO-FRICTION DIRECT DOWNLOAD
"""

import segno
from PIL import Image
import io

def forge_pure_aztec(payload_url, output_filename="konkan_aegis_transport_matrix.png"):
    print("\n[SYSTEM] INITIATING PURE PYTHON TRANSPORT MATRIX FORGE...")

    try:
        # Step 1: Generate Aztec Code (Pure Python)
        print("[SYSTEM] CALCULATING AZTEC GEOMETRY (SEGNO ENGINE)...")
        # We use a high error correction (boost_error=True) for tactical resilience
        aztec_code = segno.make(payload_url, micro=False)

        # Step 2: Render to a buffer to process with Pillow
        out = io.BytesIO()
        # Scale 10 for high resolution, border 0 to fit targeting brackets
        aztec_code.save(out, kind='png', scale=10, border=0)
        out.seek(0)
        
        raw_image = Image.open(out).convert("RGBA")
        pixel_data = raw_image.getdata()

        print("[SYSTEM] EXECUTING TACTICAL INVERSION (WHITE ON TRANSPARENT)...")
        inverted_data = []
        
        for pixel in pixel_data:
            # If pixel is Black (Barcode) -> Turn Pure White
            if pixel[0] < 128:
                inverted_data.append((255, 255, 255, 255)) 
            # If pixel is White (Background) -> Turn Transparent
            else:
                inverted_data.append((255, 255, 255, 0))

        raw_image.putdata(inverted_data)

        # Step 4: Final Asset Save
        raw_image.save(output_filename, "PNG")
        print(f"[SYSTEM] FORGE COMPLETE. ASSET SECURED: {output_filename}\n")

    except Exception as e:
        print(f"[CRITICAL] PURE FORGE FAILURE: {str(e)}")

if __name__ == "__main__":
    TARGET_URL = "https://drive.google.com/uc?export=download&id=1ZG8oZtG47afL6eEouzIa4x1qjCc48mIB"
    forge_pure_aztec(TARGET_URL)