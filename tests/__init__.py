"""Test configuration and utilities."""

import sys
from pathlib import Path

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Test constants
TEST_MODEL_NAME = "test-bmw-320i"
TEST_DATA_SIZE = 3
