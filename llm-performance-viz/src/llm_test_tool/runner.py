"""
Test runner module for LLM Test Tool.
"""

import multiprocessing as mp
from typing import Dict, List, Any

from .config import TestConfig
from .client import LlmApiClient


class TestRunner:
    """Handles execution of the LLM API test"""
    
    @staticmethod
    def run(config: TestConfig) -> List[Dict[str, Any]]:
        """Run the test with the specified configuration"""
        pool = mp.Pool(processes=config.processes)
        
        # Create unique IDs for each request
        request_ids = range(config.processes * config.requests_per_process)
        
        # Create argument list for each request
        args = [(config.model_id, config.input_tokens, config.output_tokens, 
                req_id, config.url, config.random_tokens) for req_id in request_ids]
        
        # Execute requests in parallel using process pool
        results = pool.map(LlmApiClient.send_request, args)
        
        pool.close()
        pool.join()
        
        return results