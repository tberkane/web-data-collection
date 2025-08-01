import json
from typing import List, Optional

from .configs import LLMConfig
from .prompts import GENERATE_QUERIES_PROMPT, GENERATE_QUERIES_WITH_VARIABLES_PROMPT
from .utils import perform_completion


def generate_search_queries(
    dataset_description: str,
    num_queries: int,
    llm_config: LLMConfig,
    variable_names: Optional[List[str]] = None,
) -> List[str]:
    """
    Generate Google search queries for web data collection based on dataset description.

    Args:
        dataset_description: Description of the dataset to collect data for
        num_queries: Number of search queries to generate (1-10)
        llm_config: Configuration for the LLM provider
        variable_names: Optional list of variable names to include in query templates

    Returns:
        List of search query strings
    """
    if num_queries < 1 or num_queries > 10:
        raise ValueError(f"num_queries must be between 1 and 10")

    # Generate prompt based on whether variables are provided
    if variable_names:
        prompt = GENERATE_QUERIES_WITH_VARIABLES_PROMPT.format(
            variable_names=variable_names,
            num_queries=num_queries,
            dataset_description=dataset_description,
        )
    else:
        prompt = GENERATE_QUERIES_PROMPT.format(
            num_queries=num_queries, dataset_description=dataset_description
        )

    response = perform_completion(
        prompt=prompt,
        llm_config=llm_config,
    )
    content = response.choices[0].message.content
    content = content.replace("```json", "").replace("```", "").strip()
    queries = json.loads(content)

    return queries
