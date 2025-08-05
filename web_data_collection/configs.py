from typing import Optional


class LLMConfig:
    """
    Configuration class for LLM provider settings.
    """

    def __init__(
        self,
        model: str = "openai/gpt-4.1",
        api_key: Optional[str] = None,
        temperature: Optional[float] = 0.2,
    ):
        """
        Initialize LLM configuration.

        Args:
            model: The LLM model to use (e.g., "openai/gpt-4.1")
            api_key: API key for the LLM provider
            temperature: Sampling temperature
        """
        self.model = model
        self.api_key = api_key
        self.temperature = temperature


class BrightDataConfig:
    """
    Configuration class for Bright Data API settings.
    """

    def __init__(
        self,
        api_key: str,
        zone: str,
        base_url: str = "https://api.brightdata.com/request",
    ):
        """
        Initialize Bright Data configuration.

        Args:
            api_key: Bright Data API key
            zone: Bright Data zone identifier
            base_url: Base URL for Bright Data API

        """
        self.api_key = api_key
        self.zone = zone
        self.base_url = base_url


class MistralOCRConfig:
    """
    Configuration class for Mistral OCR API settings.
    """

    def __init__(self, api_key: str):
        """
        Initialize Mistral OCR configuration.

        Args:
            api_key: Mistral OCR API key
        """
        self.api_key = api_key


class JinaConfig:
    """
    Configuration class for Jina Reranker API settings.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "jina-reranker-v2-base-multilingual",
        base_url: str = "https://api.jina.ai/v1/rerank",
    ):
        """
        Initialize Jina configuration.

        Args:
            api_key: Jina API key
            model: Jina model to use
            base_url: Jina base URL
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
