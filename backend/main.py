"""
main.py
-------
CLI entrypoint for the Part 1 pipeline.

Usage:
    python main.py <image_path> "<title>" "<author>"

Examples:
    python main.py my_sketch.jpg "Forest Scene" "Ankur"
    python main.py stolen_copy.png "Someone Else's Art" "Thief"

For viewing the current registry:
    python registry.py
"""

import sys
from pipeline import process_upload, print_result


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python main.py <image_path> <title> <author>")
        print('Example: python main.py sketch.jpg "My Sketch" "Ankur"')
        sys.exit(1)

    filepath = sys.argv[1]
    title    = sys.argv[2]
    author   = sys.argv[3]

    result = process_upload(filepath, title, author)
    print_result(result)
