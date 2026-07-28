"""
validator.py
------------
Step 1 of the pipeline: validate and normalise the uploaded image.

Handles all sketch types observed in empirical testing:
  - Digital artwork (clean file, white/kraft background)
  - Photo of physical sketchbook (page curve, hand, binding, wall bg)
  - Photo of notebook paper (lines, spiral holes, table bg)
  - Instagram/TikTok screenshots (UI chrome, like counts, handles)

The normalised image returned here is used by BOTH the hasher (pHash)
and the SIFT engine — so preprocessing happens exactly once.
"""

import cv2
import numpy as np
from PIL import Image, ImageOps, ImageFilter
import os

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MAX_FILE_SIZE_MB   = 20
MIN_DIMENSION      = 100   # reject tiny thumbnails
TARGET_LONG_EDGE   = 1024  # normalise to this for consistent SIFT keypoint density


class ValidationError(Exception):
    pass


def validate_and_preprocess(filepath: str) -> tuple[np.ndarray, np.ndarray]:
    """
    Validates an uploaded sketch image and returns two versions:

    Returns:
        (raw_gray, processed_gray)
        raw_gray       : grayscale numpy array at original resolution
                         used only for SIFT (which benefits from full res)
        processed_gray : normalised 256x256 PIL-compatible numpy array
                         used for pHash computation

    Raises:
        ValidationError with a human-readable reason on failure.
    """
    # 1. Extension
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
        )

    # 2. File size
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValidationError(
            f"File too large ({size_mb:.1f} MB). Max is {MAX_FILE_SIZE_MB} MB."
        )

    # 3. Open + corruption check
    try:
        img_bgr = cv2.imread(filepath)
        if img_bgr is None:
            raise ValueError("cv2.imread returned None")
    except Exception as e:
        raise ValidationError(f"Cannot open image (corrupted or unreadable): {e}")

    # 4. Minimum dimensions
    h, w = img_bgr.shape[:2]
    if w < MIN_DIMENSION or h < MIN_DIMENSION:
        raise ValidationError(
            f"Image too small ({w}x{h}px). Minimum is {MIN_DIMENSION}x{MIN_DIMENSION}."
        )

    # 5. Convert to grayscale
    raw_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 6. Resize for SIFT — normalise long edge to TARGET_LONG_EDGE
    #    keeps aspect ratio, gives SIFT consistent keypoint density
    #    regardless of whether input is 600px or 4000px
    scale = TARGET_LONG_EDGE / max(h, w)
    if scale < 1.0:  # only downscale, never upscale
        new_w = int(w * scale)
        new_h = int(h * scale)
        raw_gray = cv2.resize(raw_gray, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # 7. Processed version for pHash
    #    autocontrast normalises lighting (handles paper/phone camera variation)
    #    mild blur kills JPEG block artifacts and paper grain noise
    pil = Image.fromarray(raw_gray)
    pil = ImageOps.autocontrast(pil, cutoff=2)
    pil = pil.filter(ImageFilter.GaussianBlur(radius=1.0))
    pil = pil.resize((256, 256), Image.LANCZOS)
    processed_gray = np.array(pil)

    return raw_gray, processed_gray


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        try:
            raw, proc = validate_and_preprocess(sys.argv[1])
            print(f"OK — raw: {raw.shape}, processed: {proc.shape}")
        except ValidationError as e:
            print(f"Validation failed: {e}")
    else:
        print("Usage: python validator.py <image_path>")
