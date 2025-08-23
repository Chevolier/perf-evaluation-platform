#!/usr/bin/env python3
"""
Standalone deployment script for vLLM/SGLang servers.
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from llm_test_tool.deploy_only import main

if __name__ == "__main__":
    main()