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

## Dependencies

- `litellm`: LLM provider interface
- `crawl4ai`: Web crawling and extraction
- `mistralai`: PDF OCR processing
- `htmldate`: Date extraction from web pages
- `requests`: HTTP requests
