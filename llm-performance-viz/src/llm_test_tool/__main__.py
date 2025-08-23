"""
Entry point for running the package as a module.
"""

import sys
from .main import main
from .auto_test import main as auto_test_main
from .deploy_only import main as deploy_main
from .viz_server import main as viz_main

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "auto-test":
            # Remove the auto-test argument and pass the rest to auto_test_main
            sys.argv = [sys.argv[0]] + sys.argv[2:]
            auto_test_main()
        elif sys.argv[1] == "deploy":
            # Remove the deploy argument and pass the rest to deploy_main
            sys.argv = [sys.argv[0]] + sys.argv[2:]
            deploy_main()
        elif sys.argv[1] == "viz":
            # Remove the viz argument and pass the rest to viz_main
            sys.argv = [sys.argv[0]] + sys.argv[2:]
            viz_main()
        else:
            main()
    else:
        main()