# Web Data Collection

A Python library for automated web data collection using LLMs. This tool enables structured data extraction from web pages through LLM-powered search, retrieval, extraction, and quality control.

## Features

- **Search Query Generation**: Automatically generates template-based search queries from a dataset description using an LLM
- **Web Page Retrieval**: Retrieves web pages with support for:
  - Search results filtering using reranking
  - Date range filtering
  - Geographic filtering
  - News-only searches
  - Media Cloud source filtering
  - Time chunking for large date ranges
- **Data Extraction**: Extracts structured data from web pages using an LLM with:
  - Custom extraction schemas
  - PDF text extraction via Mistral OCR
  - Grounding verification
  - Source attribution
- **Quality Control**: Flags datapoints with potential issues using an LLM

## Quick Start

```bash
pip install -r requirements.txt
```

See `example.ipynb` for a working example demonstrating the full pipeline.

## Configuration

Set up the following environment variables:

```bash
OPENAI_API_KEY=your_openai_api_key # or any other LLM provider
BRIGHT_DATA_API_KEY=your_bright_data_api_key # for web page retrieval
BRIGHT_DATA_ZONE=your_bright_data_zone # for web page retrieval
MISTRAL_API_KEY=your_mistral_api_key # optional, for PDF processing
```


## Advanced Usage

### Date Range Filtering

```python
webpages = retrieve_webpages(
    query_templates,
    results_pages_per_query=1,
    bright_data_config=bright_data_config,
    variables=variables,
    start_date="2020-01-01",
    end_date="2022-12-31",
    time_chunking=True  # Split large date ranges into chunks
)
```

### Geographic Filtering

```python
webpages = retrieve_webpages(
    query_templates,
    results_pages_per_query=1,
    bright_data_config=bright_data_config,
    variables=variables,
    media_cloud_country="United States", # restrict the search to websites in the Media Cloud US collection
    geolocation_country="United States" # execute the search as if it originated from the US
)
```

### PDF Handling

```python
from web_data_collection import MistralOCRConfig

mistral_ocr_config = MistralOCRConfig(api_key=os.environ.get("MISTRAL_API_KEY"))

extracted_data = await extract_data(
    urls=urls,
    schema=schema,
    llm_config=llm_config,
    handle_pdfs=True,
    mistral_ocr_config=mistral_ocr_config
)
```

### Result Reranking

```python
from web_data_collection import Reranker

reranker = Reranker(model_name="mixedbread-ai/mxbai-rerank-xsmall-v1")
reranking_scores = reranker.rerank_results(
    queries=[page["query"] for page in webpages],
    documents=[page["title"] for page in webpages]
)
```

## Dependencies

- `litellm`: LLM provider interface
- `crawl4ai`: Web crawling and extraction
- `sentence-transformers`: Result reranking
- `mistralai`: PDF OCR processing
- `htmldate`: Date extraction from web pages
- `requests`: HTTP requests
