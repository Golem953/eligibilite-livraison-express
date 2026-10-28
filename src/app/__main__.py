"""Permet `python -m livraison_express ...`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())