"""Allow running EPL as `python -m epl <file.epl>` or `epl <file.epl>`."""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.cli import main

if __name__ == "__main__":
    main()
