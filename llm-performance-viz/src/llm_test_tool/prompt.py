"""
Prompt generation module for LLM Test Tool.

This module provides functionality to generate prompts with both fixed and random components,
which can leverage prompt caching features in vLLM and similar systems.
"""

import random
import string
import uuid
from typing import Tuple

# Constant fixed part with single-digit numbers
# This will be the same for all requests to ensure consistent caching
FIXED_PROMPT = "5 3 5 1 1 7 7 7 1 2 9 4 3 3 8 6 6 4 9 2 9 7 2 9 1 2 9 2 6 5 8 8 3 3 1 3 7 6 9 5 1 2 8 0 4 9 5 0 9 8 6 0 8 8 9 7 5 5 5 8 1 2 9 0 5 6 8 9 4 2 2 2 1 0 7 0 7 4 5 4 0 5 4 7 7 2 8 4 2 4 9 2 9 0 1 7 5 8 2 1 "
FIXED_PROMPT_LENGTH = len(FIXED_PROMPT.split()) * 2
FINAL_PROMPT = "please repeat these number 10000 times"
FINAL_PROMPT_LENGTH = len(FINAL_PROMPT.split()) * 2

class PromptGenerator:
    """
    Handles generation of prompts with specified token lengths.
    
    The prompts are split into fixed and random parts to leverage prompt caching
    in systems like vLLM. The fixed part remains constant across requests,
    allowing for cache hits, while the random part ensures unique requests.
    """
    
    @staticmethod
    def generate(total_length: int, fixed_length: int) -> str:
        """
        Generate a prompt with specified fixed and random token lengths.
        
        Args:
            total_length: Total approximate token length
            fixed_length: Number of fixed tokens (for caching)
        
        Returns:
            A string with the specified approximate token length
        """
        if total_length <= 0:
            return ""
        # return FINAL_PROMPT
        # Ensure fixed_length doesn't exceed total_length
        fixed_length = min(fixed_length, total_length)
        random_length = total_length - fixed_length
        
        fixed_part = "".join(fixed_length // FIXED_PROMPT_LENGTH * [FIXED_PROMPT]) + FIXED_PROMPT[:fixed_length // 2 % FIXED_PROMPT_LENGTH * 2]
        random_part = "".join([f"{random.randint(0, 9)} " for _ in range((random_length - FINAL_PROMPT_LENGTH) // 2)])
        return fixed_part + random_part + FINAL_PROMPT