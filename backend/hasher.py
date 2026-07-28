"""
hasher.py
---------
Generates pHash from the preprocessed image.

Role in the pipeline (empirically established across 6 real sketch pairs):
  - pHash is NOT the similarity detector — it scored 24–34/64 on all 6
    real copies and would miss every attack at any reasonable threshold
  - pHash IS a fast coarse pre-filter:
      distance <= 10  → instant MATCH (exact repost, zero processing needed)
      distance >  10  → pass to SIFT+RANSAC for real detection
  - Eliminates ~99% of unrelated registry images before SIFT runs,
    keeping the system fast as the registry grows

dHash is intentionally dropped — empirical data showed it added no
additional signal over pHash for this attack type (crop/zoom/filter),
and SIFT already handles everything dHash was supposed to catch.
"""

import imagehash
import numpy as np
from PIL import Image

HASH_SIZE = 8          # 8x8 = 64-bit hash
PHASH_EXACT_THRESHOLD = 10   # <= this = instant match, skip SIFT


def compute_phash(processed_gray: np.ndarray) -> str:
    """
    Computes pHash from a preprocessed (256x256, normalised) grayscale image.

    Args:
        processed_gray: numpy array from validator.validate_and_preprocess()[1]

    Returns:
        pHash as hex string e.g. 'a3f1b2c4d5e6f708'
    """
    pil = Image.fromarray(processed_gray)
    return str(imagehash.phash(pil, hash_size=HASH_SIZE))


def phash_distance(hash1: str, hash2: str) -> int:
    """Hamming distance between two pHash hex strings."""
    return imagehash.hex_to_hash(hash1) - imagehash.hex_to_hash(hash2)


def is_exact_match(hash1: str, hash2: str) -> bool:
    """True if two images are near-identical (no need to run SIFT)."""
    return phash_distance(hash1, hash2) <= PHASH_EXACT_THRESHOLD


if __name__ == "__main__":
    import sys
    from validator import validate_and_preprocess, ValidationError
    if len(sys.argv) > 1:
        try:
            _, proc = validate_and_preprocess(sys.argv[1])
            ph = compute_phash(proc)
            print(f"pHash: {ph}")
        except ValidationError as e:
            print(f"Error: {e}")
    else:
        print("Usage: python hasher.py <image_path>")
