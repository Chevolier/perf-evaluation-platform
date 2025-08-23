"""
Main entry point for LLM Test Tool.
"""

import time

from .config import parse_arguments, print_test_config
from .runner import TestRunner
from .analyzer import ResultAnalyzer


def main():
    """Main entry point for the application"""
    # Parse command line arguments
    config = parse_arguments()
    
    # Print test configuration
    print_test_config(config)
    
    # Run the test
    start_time = time.time()
    results = TestRunner.run(config)
    total_time = time.time() - start_time
    
    # Analyze results
    analysis = ResultAnalyzer.analyze(results, total_time, config)
    
    # Save results to file
    ResultAnalyzer.save_results(analysis, config.output_file)
    
    # Print summary
    ResultAnalyzer.print_summary(analysis)


if __name__ == "__main__":
    main()