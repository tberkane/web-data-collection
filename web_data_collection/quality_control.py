import io
from typing import Dict, List

import pandas as pd

from .configs import LLMConfig
from .prompts import QUALITY_CONTROL_PROMPT
from .utils import perform_completion


def control_quality(
    extracted_data: List[Dict[str, str]],
    dataset_description: str,
    llm_config: LLMConfig,
) -> Dict[str, str]:
    """
    Control the quality of the extracted data by having an LLM check for issues in each datapoint.

    Args:
        extracted_data: List of extracted data
        dataset_description: Description of the dataset
        llm_config: Configuration for the LLM provider

    Returns:
        Dict[str, str]: Dictionary of issues found in the extracted data
    """
    df = pd.DataFrame(extracted_data)
    if "url" in df.columns:
        df = df.drop("url", axis=1)

    if "id" in df.columns:
        df.index = df["id"]
        df = df.drop("id", axis=1)
    else:
        df.index = df.index + 1
    df = df.rename(columns={"index": "id"})

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=True)
    csv_string = csv_buffer.getvalue()

    prompt = QUALITY_CONTROL_PROMPT.format(
        dataset_description=dataset_description,
        extracted_data=csv_string,
    )

    response = perform_completion(
        prompt=prompt,
        llm_config=llm_config,
    )
    content = response.choices[0].message.content

    issues = {}
    for line in content.strip().split("\n"):
        if ":" in line:
            idx, issue = line.split(":", 1)
            idx = int(idx.strip())
            issues[str(idx)] = issue.strip()

    return issues
