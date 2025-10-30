from typing import Dict, Iterator, List

from evalscope.perf.arguments import Arguments
from evalscope.perf.plugin.datasets.base import DatasetPluginBase
from evalscope.perf.plugin.registry import register_dataset
import json


@register_dataset('custom')
class CustomDatasetPlugin(DatasetPluginBase):
    """Read dataset and return prompt.
    """

    def __init__(self, query_parameters: Arguments):
        super().__init__(query_parameters)

    def build_messages(self) -> Iterator[List[Dict]]:
        for item in self.dataset_line_by_line(self.query_parameters.dataset_path):
            if item.strip():
                prompt = json.loads(item.strip())['prompt']
                if len(prompt) > self.query_parameters.min_prompt_length and len(
                    prompt
                ) < self.query_parameters.max_prompt_length:
                    if self.query_parameters.apply_chat_template:
                        message = self.create_message(prompt)
                        yield [message]
                    else:
                        yield prompt


if __name__ == '__main__':
    from evalscope.perf.arguments import Arguments
    from evalscope.perf.main import run_perf_benchmark

    args = Arguments(
        model='/home/ec2-user/SageMaker/efs/Models/Qwen3-8B',
        url='http://localhost:8000/v1/chat/completions',
        dataset_path='/home/ec2-user/SageMaker/efs/Projects/text-to-sql/data/stress_test_v3.jsonl',
        api_key='EMPTY',
        dataset='custom',
    )

    run_perf_benchmark(args)
