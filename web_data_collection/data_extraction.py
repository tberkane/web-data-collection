import json
import re
import urllib.parse
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from crawl4ai import LLMConfig as Crawl4aiLLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from litellm import completion
from mistralai import Mistral
from pydantic import BaseModel, Field

from .configs import LLMConfig, MistralOCRConfig
from .prompts import GENERATE_EXTRACTION_SCHEMA_PROMPT
from .utils import perform_completion


def generate_extraction_schema(
    dataset_description: str, schema_fields: List[str], llm_config: LLMConfig
) -> str:
    """
    Generate a schema representing the fields to extract from a webpage.

    Args:
        dataset_description: Description of the dataset we are collecting
        schema_fields: List of fields to extract from the webpage
        llm_config: Configuration for the LLM provider

    Returns:
        str: A string representing the schema
    """
    prompt = GENERATE_EXTRACTION_SCHEMA_PROMPT.format(
        dataset_description=dataset_description,
        schema_fields=schema_fields,
    )
    response = perform_completion(prompt, llm_config)
    content = response.choices[0].message.content

    return content


def _extract_pdf_text(url: str, mistral_ocr_config: MistralOCRConfig) -> str:
    """
    Extract the text from a PDF url.

    Args:
        url: The URL of the PDF to extract text from
        mistral_ocr_config: Configuration for the Mistral OCR API

    Returns:
        str: The extracted text from the PDF
    """
    client = Mistral(api_key=mistral_ocr_config.api_key)
    ocr_response = client.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "document_url", "document_url": url},
        include_image_base64=False,
    )
    text = "\n".join([page.markdown for page in ocr_response.pages])
    return text


def _remove_markdown_links(text: str) -> str:
    """
    Remove all links and images from a markdown-formatted string.

    Args:
        text: The markdown-formatted string to remove links and images from

    Returns:
        str: The markdown-formatted string with links and images removed
    """
    # Remove inline links [text](url)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove reference links [text][ref] and [ref]: url
    text = re.sub(r"\[([^\]]+)\]\[[^\]]+\]", r"\1", text)
    text = re.sub(r"^\[[^\]]+\]:\s*.*$", "", text, flags=re.MULTILINE)
    # Remove images ![alt text](url)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    # Remove empty links []()
    text = re.sub(r"\[\]\([^)]+\)", "", text)
    return text


def _check_grounding(
    datapoint: Dict[str, Any], webpage_markdown: str
) -> Tuple[bool, str]:
    """
    Check if the datapoint's grounding quote is present in the webpage markdown.

    Args:
        datapoint: The datapoint to check grounding for. Must contain a "grounding_quote" field.
        webpage_markdown: The markdown-formatted string of the webpage

    Returns:
        bool: True if the datapoint's grounding quote is present in the webpage markdown, False otherwise
        str: The webpage markdown with the grounding quote removed
    """
    grounding = datapoint.get("grounding_quote")
    if not grounding:
        return False, None
    grounding = "".join(c for c in grounding if c.isalnum())
    webpage_markdown = "".join(
        c for c in _remove_markdown_links(webpage_markdown) if c.isalnum()
    )
    return grounding in webpage_markdown, webpage_markdown


async def extract_data(
    urls: List[str],
    schema: str,
    llm_config: LLMConfig,
    extra_instruction: Optional[str] = None,
    handle_pdfs: bool = False,
    mistral_ocr_config: MistralOCRConfig = None,
) -> List[Dict[str, Any]]:
    """
    Extract data from a list of URLs using a schema.

    Args:
        urls: List of URLs to extract data from
        schema: Schema to use for extraction
        llm_config: Configuration for the LLM provider
        extra_instruction: Extra instruction for data extraction
        handle_pdfs: Whether to handle PDFs. If True, mistral_ocr_config is required
        mistral_ocr_config: Configuration for the Mistral OCR API

    Returns:
        List[Dict[str, Any]]: List of extracted data
    """
    namespace = {
        "BaseModel": BaseModel,
        "Field": Field,
        "Optional": Optional,
        "List": List,
    }
    schema += '\n    grounding_quote: str = Field(..., description="Short span of text taken verbatim from the webpage from which the data is extracted (just a few words), EXACTLY as it appears in the text, DO NOT miss any words in the middle. DO NOT include \\\\ before apostrophes or other special characters.")'
    class_name = schema.split("class ")[1].split("(")[0].strip()
    exec(schema, namespace)
    Schema = namespace[class_name]

    instruction = f"From the crawled content, extract all mentioned {class_name}. Only extract a value if it matches what the field describes - no related or similar information. "
    if extra_instruction:
        instruction += extra_instruction

    run_config = CrawlerRunConfig(
        extraction_strategy=LLMExtractionStrategy(
            llm_config=Crawl4aiLLMConfig(
                provider=llm_config.model,
                api_token=llm_config.api_key,
            ),
            schema=Schema.model_json_schema(),
            extraction_type="schema",
            instruction=instruction,
            input_format="markdown",
        ),
        cache_mode=CacheMode.BYPASS,
    )

    browser_config = BrowserConfig(verbose=True)
    async with AsyncWebCrawler(config=browser_config) as crawler:
        extracted_data = []
        for url in urls:
            if ".pdf" in url:
                if not handle_pdfs:
                    continue
                if not mistral_ocr_config:
                    raise ValueError(
                        "mistral_ocr_config is required when handle_pdfs is True"
                    )
                to_extract = f"raw:{_extract_pdf_text(url, mistral_ocr_config)}"
            else:
                to_extract = url

            result = await crawler.arun(url=to_extract, config=run_config)
            if result and result.extracted_content:
                try:
                    data = json.loads(result.extracted_content)
                    for datapoint in data:
                        if not datapoint.get("error"):
                            is_grounded, _ = _check_grounding(
                                datapoint, result.markdown
                            )
                            datapoint["is_grounded"] = is_grounded
                            if is_grounded:
                                datapoint["source"] = (
                                    f"{url}#:~:text={urllib.parse.quote(datapoint['grounding_quote'])}"
                                )
                            else:
                                datapoint["source"] = url
                            datapoint.pop("error")
                            extracted_data.append(datapoint)
                except json.JSONDecodeError:
                    continue

    return extracted_data


async def extract_data_streaming(
    urls: List[str],
    schema: str,
    llm_config: LLMConfig,
    extra_instruction: Optional[str] = None,
    handle_pdfs: bool = False,
    mistral_ocr_config: MistralOCRConfig = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Extract data from a list of URLs using a schema and stream results as they come in.

    Args:
        urls: List of URLs to extract data from
        schema: Schema to use for extraction
        llm_config: Configuration for the LLM provider
        extra_instruction: Extra instruction for data extraction
        handle_pdfs: Whether to handle PDFs. If True, mistral_ocr_config is required
        mistral_ocr_config: Configuration for the Mistral OCR API

    Yields:
        Dict[str, Any]: Extracted datapoint as it's processed or {"url_done": url} if the url is done being processed
    """
    namespace = {
        "BaseModel": BaseModel,
        "Field": Field,
        "Optional": Optional,
        "List": List,
    }
    schema += '\n    grounding_quote: str = Field(..., description="Short span of text taken verbatim from the webpage from which the data is extracted (just a few words), EXACTLY as it appears in the text, DO NOT miss any words in the middle. DO NOT include \\\\ before apostrophes or other special characters.")'
    class_name = schema.split("class ")[1].split("(")[0].strip()
    exec(schema, namespace)
    Schema = namespace[class_name]

    instruction = f"From the crawled content, extract all mentioned {class_name}. Only extract a value if it matches what the field describes - no related or similar information. "
    if extra_instruction:
        instruction += extra_instruction

    run_config = CrawlerRunConfig(
        extraction_strategy=LLMExtractionStrategy(
            llm_config=Crawl4aiLLMConfig(
                provider=llm_config.model,
                api_token=llm_config.api_key,
            ),
            schema=Schema.model_json_schema(),
            extraction_type="schema",
            instruction=instruction,
            input_format="markdown",
        ),
        cache_mode=CacheMode.BYPASS,
    )

    browser_config = BrowserConfig(verbose=True)
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in urls:
            if ".pdf" in url:
                if not handle_pdfs:
                    yield {"url_done": url}
                    continue
                if not mistral_ocr_config:
                    raise ValueError(
                        "mistral_ocr_config is required when handle_pdfs is True"
                    )
                to_extract = f"raw:{_extract_pdf_text(url, mistral_ocr_config)}"
            else:
                to_extract = url

            result = await crawler.arun(url=to_extract, config=run_config)
            if result and result.extracted_content:
                try:
                    data = json.loads(result.extracted_content)
                    for datapoint in data:
                        if not datapoint.get("error"):
                            is_grounded, _ = _check_grounding(
                                datapoint, result.markdown
                            )
                            datapoint["is_grounded"] = is_grounded
                            if is_grounded:
                                datapoint["source"] = (
                                    f"{url}#:~:text={urllib.parse.quote(datapoint['grounding_quote'])}"
                                )
                            else:
                                datapoint["source"] = url
                            datapoint.pop("error")
                            yield datapoint
                except json.JSONDecodeError:
                    yield {"url_done": url}
                    continue
            yield {"url_done": url}
