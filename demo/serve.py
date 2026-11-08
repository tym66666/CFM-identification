"""Run from the repository root: python demo/serve.py."""
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo.backend.server import main

if __name__ == '__main__':
    main()
