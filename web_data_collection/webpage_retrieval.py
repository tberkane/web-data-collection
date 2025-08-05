import itertools
import json
import logging
import os
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

import requests
from htmldate import find_date

from .configs import BrightDataConfig, JinaConfig
from .utils import timeout_function

# Configure logging
logger = logging.getLogger(__name__)

# File paths
MODULE_DIR = Path(__file__).parent
DATA_DIR = MODULE_DIR / "data"
COUNTRY_TO_CODE_FILE = DATA_DIR / "country_to_code.json"
COUNTRY_TO_MC_SOURCES_FILE = DATA_DIR / "country_to_mc_sources.json"


def retrieve_webpages(
    search_query_templates: List[str],
    results_pages_per_query: int,
    bright_data_config: BrightDataConfig,
    search_query_variables: Optional[Dict[str, List[str]]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    time_chunking: bool = False,
    media_cloud_country: Optional[str] = None,
    geolocation_country: Optional[str] = None,
    news_only: bool = False,
) -> Dict[Optional[Tuple[str, ...]], Dict[str, List[Dict[str, str]]]]:
    """
    Retrieve webpages based on search query templates.

    Args:
        search_query_templates: List of search query templates
        results_pages_per_query: Number of result pages to retrieve per query
        bright_data_config: Bright Data API configuration
        search_query_variables: Dictionary mapping variable names to possible values
        start_date: Start date for search filtering (YYYY-MM-DD format)
        end_date: End date for search filtering (YYYY-MM-DD format)
        time_chunking: Whether to split date range into chunks
        media_cloud_country: Country for Media Cloud source filtering
        geolocation_country: Country for geolocation filtering
        news_only: Whether to search only news results

    Returns:
        Dictionary mapping variable combinations to queries to their results
    """
    try:

        # Expand query templates
        search_queries, variable_value_combinations = _expand_query_templates(
            search_query_templates, search_query_variables
        )
        logger.debug(
            f"Expanded {len(search_query_templates)} templates into {len(search_queries)} queries"
        )

        # Handle date chunking
        date_chunks = _get_date_chunks_for_retrieval(
            start_date, end_date, time_chunking
        )

        # Get Media Cloud sources if specified
        media_cloud_sources = _get_media_cloud_sources_if_needed(media_cloud_country)

        # Process queries and retrieve results
        return _process_queries_and_retrieve_results(
            search_queries,
            variable_value_combinations,
            date_chunks,
            results_pages_per_query,
            bright_data_config,
            media_cloud_sources,
            geolocation_country,
            news_only,
        )

    except Exception as e:
        logger.error(f"Error in retrieve_webpages: {e}")
        raise Exception(f"Failed to retrieve webpages: {e}") from e


def retrieve_webpages_streaming(
    search_query_templates: List[str],
    results_pages_per_query: int,
    bright_data_config: BrightDataConfig,
    search_query_variables: Optional[Dict[str, List[str]]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    time_chunking: bool = False,
    media_cloud_country: Optional[str] = None,
    geolocation_country: Optional[str] = None,
    news_only: bool = False,
    variable_name_with_assigned_countries: Optional[str] = None,
    variable_values_media_cloud_countries: Optional[Dict[str, str]] = None,
    variable_values_geolocation_countries: Optional[Dict[str, str]] = None,
) -> Generator[Tuple[Optional[Tuple[str, ...]], str, Dict[str, str]], None, None]:
    """
    Retrieve webpages based on search query templates and stream results as they come in.

    Args:
        search_query_templates: List of search query templates
        results_pages_per_query: Number of result pages to retrieve per query
        bright_data_config: Bright Data API configuration
        search_query_variables: Dictionary mapping variable names to possible values
        start_date: Start date for search filtering (YYYY-MM-DD format)
        end_date: End date for search filtering (YYYY-MM-DD format)
        time_chunking: Whether to split date range into chunks
        media_cloud_country: Country for Media Cloud source filtering
        geolocation_country: Country for geolocation filtering
        news_only: Whether to search only news results
        variable_name_with_assigned_countries: Name of the variable whose values we are assigning countries to
        variable_values_media_cloud_countries: Dictionary mapping variable values to Media Cloud countries
        variable_values_geolocation_countries: Dictionary mapping variable values to geolocation countries

    Yields:
        Tuple containing:
            - variable_value_combo: The variable value combination for this query (or None)
            - query: The search query that produced this result
            - result: Dictionary containing the search result (link, title, description, etc.)
    """
    assert not (
        variable_name_with_assigned_countries
        and (media_cloud_country or geolocation_country)
    ), "Assign country either globally or per variable value but not both"

    try:
        # Expand query templates
        search_queries, variable_value_combinations = _expand_query_templates(
            search_query_templates, search_query_variables
        )
        logger.debug(
            f"Expanded {len(search_query_templates)} templates into {len(search_queries)} queries"
        )

        # Handle date chunking
        date_chunks = _get_date_chunks_for_retrieval(
            start_date, end_date, time_chunking
        )

        # Get Media Cloud sources if specified
        media_cloud_sources = _get_media_cloud_sources_if_needed(media_cloud_country)

        if (
            variable_name_with_assigned_countries
            and variable_values_media_cloud_countries
        ):
            variable_values_media_cloud_sources = {
                value: _get_media_cloud_sources_if_needed(media_cloud_country)
                for value, media_cloud_country in variable_values_media_cloud_countries.items()
            }
        else:
            variable_values_media_cloud_sources = None

        # Process queries and stream results
        yield from _process_queries_and_stream_results(
            search_queries,
            variable_value_combinations,
            date_chunks,
            results_pages_per_query,
            bright_data_config,
            media_cloud_sources,
            geolocation_country,
            news_only,
            variable_name_with_assigned_countries,
            variable_values_media_cloud_sources,
            variable_values_geolocation_countries,
            search_query_variables,
        )

    except Exception as e:
        logger.error(f"Error in retrieve_webpages_streaming: {e}")
        raise Exception(f"Failed to retrieve webpages: {e}") from e


def _get_date_chunks_for_retrieval(
    start_date: Optional[str], end_date: Optional[str], time_chunking: bool
) -> List[Dict[str, str]]:
    """
    Get date chunks for retrieval.

    Args:
        start_date: Start date for search filtering (YYYY-MM-DD format)
        end_date: End date for search filtering (YYYY-MM-DD format)
        time_chunking: Whether to split date range into chunks

    Returns:
        List of dictionaries containing start and end dates for each chunk
    """
    if time_chunking:
        date_chunks = _get_date_chunks(start_date, end_date)
        logger.debug(f"Created {len(date_chunks)} date chunks for time chunking")
    else:
        date_chunks = [{"start": start_date, "end": end_date}]

    return date_chunks


def _get_media_cloud_sources_if_needed(
    media_cloud_country: Optional[str],
) -> Optional[List[str]]:
    """
    Get Media Cloud sources if country is specified.

    Args:
        media_cloud_country: Country name to get Media Cloud sources for

    Returns:
        List of Media Cloud source URLs if country is specified, None otherwise
    """
    if media_cloud_country:
        media_cloud_sources = get_media_cloud_sources(media_cloud_country)
        logger.debug(
            f"Retrieved {len(media_cloud_sources)} Media Cloud sources for {media_cloud_country}"
        )
        return media_cloud_sources
    return None


def _get_variable_value_for_country_assignment(
    variable_value_combo: Optional[Tuple[str, ...]],
    variable_name_with_assigned_countries: str,
    search_query_variables: Optional[Dict[str, List[str]]] = None,
) -> Optional[str]:
    """
    Get the variable value that corresponds to the variable_name_with_assigned_countries.

    Args:
        variable_value_combo: The variable value combination for this query
        variable_name_with_assigned_countries: Name of the variable whose values we are assigning countries to
        search_query_variables: Dictionary mapping variable names to possible values

    Returns:
        The variable value that corresponds to the variable_name_with_assigned_countries, or None if not found
    """
    if not variable_value_combo or not search_query_variables:
        return None

    # Normalize variable names to match the format used in _expand_query_templates
    normalized_variable_names = {
        k.lower().replace(" ", "_"): k for k in search_query_variables.keys()
    }

    # Find the normalized name for the variable we're looking for
    target_normalized_name = variable_name_with_assigned_countries.lower().replace(
        " ", "_"
    )

    if target_normalized_name not in normalized_variable_names:
        logger.warning(
            f"Variable '{variable_name_with_assigned_countries}' not found in search_query_variables"
        )
        return None

    # Get the original variable name
    original_var_name = normalized_variable_names[target_normalized_name]

    # Find the position of this variable in the search_query_variables
    var_names = list(search_query_variables.keys())
    try:
        var_index = var_names.index(original_var_name)
        if var_index < len(variable_value_combo):
            return variable_value_combo[var_index]
    except (ValueError, IndexError):
        logger.warning(
            f"Could not find variable '{original_var_name}' in variable value combination"
        )

    return None


def _process_queries_and_retrieve_results(
    search_queries: List[str],
    variable_value_combinations: List[Optional[Tuple[str, ...]]],
    date_chunks: List[Dict[str, str]],
    results_pages_per_query: int,
    bright_data_config: BrightDataConfig,
    media_cloud_sources: Optional[List[str]],
    geolocation_country: Optional[str],
    news_only: bool,
) -> Dict[Optional[Tuple[str, ...]], Dict[str, List[Dict[str, str]]]]:
    """
    Process queries and retrieve results from all date chunks.

    Args:
        search_queries: List of search query strings to process
        variable_value_combinations: List of variable value combinations corresponding to each query
        date_chunks: List of date range dictionaries with 'start' and 'end' keys
        results_pages_per_query: Number of result pages to retrieve per query
        bright_data_config: Configuration for Bright Data API
        media_cloud_sources: Optional list of Media Cloud source URLs to filter by
        geolocation_country: Optional country code for geolocation filtering
        news_only: Whether to retrieve only news results

    Returns:
        Dictionary mapping variable value combinations to queries to their results
    """
    results: Dict[Optional[Tuple[str, ...]], Dict[str, List[Dict[str, str]]]] = {}
    seen_urls = set()

    for query, variable_value_combo in zip(search_queries, variable_value_combinations):
        logger.debug(
            f"Processing query: {query}, variable value combo: {variable_value_combo}"
        )

        if variable_value_combo not in results:
            results[variable_value_combo] = {}

        # Process each date chunk
        chunk_results = _process_date_chunks(
            query,
            date_chunks,
            results_pages_per_query,
            bright_data_config,
            media_cloud_sources,
            geolocation_country,
            news_only,
            seen_urls,
        )

        results[variable_value_combo][query] = chunk_results

    return results


def _process_date_chunks(
    query: str,
    date_chunks: List[Dict[str, str]],
    results_pages_per_query: int,
    bright_data_config: BrightDataConfig,
    media_cloud_sources: Optional[List[str]],
    geolocation_country: Optional[str],
    news_only: bool,
    seen_urls: set,
) -> List[Dict[str, str]]:
    """
    Process all date chunks for a single query.

    Args:
        query: Search query string to process
        date_chunks: List of date range dictionaries with 'start' and 'end' keys
        results_pages_per_query: Number of result pages to retrieve per query
        bright_data_config: Configuration for Bright Data API
        media_cloud_sources: Optional list of Media Cloud source URLs to filter by
        geolocation_country: Optional country code for geolocation filtering
        news_only: Whether to retrieve only news results
        seen_urls: Set of URLs already processed to avoid duplicates

    Returns:
        List of search result dictionaries from all date chunks
    """
    all_chunk_results = []

    for chunk in date_chunks:
        logger.debug(f"Processing date chunk: {chunk['start']} to {chunk['end']}")

        chunk_results = _retrieve_bright_data_results(
            query,
            results_pages_per_query,
            bright_data_config,
            chunk["start"],
            chunk["end"],
            media_cloud_sources,
            geolocation_country,
            news_only,
        )

        # Filter out duplicate URLs
        unique_results = [r for r in chunk_results if r["link"] not in seen_urls]
        seen_urls.update([r["link"] for r in unique_results])
        all_chunk_results.extend(unique_results)

    return all_chunk_results


def _retrieve_bright_data_results(
    query: str,
    results_pages_per_query: int,
    bright_data_config: BrightDataConfig,
    start_date: Optional[str],
    end_date: Optional[str],
    media_cloud_sources: Optional[List[str]],
    geolocation_country: Optional[str],
    news_only: bool,
    num_mc_sites: int = 50,
) -> List[Dict[str, str]]:
    """
    Retrieve search results from Bright Data API for a given query.

    Args:
        query: Search query string
        results_pages_per_query: Number of result pages to retrieve
        bright_data_config: Configuration for Bright Data API
        start_date: Start date for search filtering (YYYY-MM-DD format)
        end_date: End date for search filtering (YYYY-MM-DD format)
        media_cloud_sources: Optional list of Media Cloud source URLs to filter by
        geolocation_country: Optional country name for geolocation filtering
        news_only: Whether to retrieve only news results
        num_mc_sites: Maximum number of Media Cloud sites to include in query

    Returns:
        List of search result dictionaries
    """
    # Build query with date filters
    date_filters = []
    if start_date:
        date_filters.append(f"after:{start_date}")
    if end_date:
        date_filters.append(f"before:{end_date}")
    if date_filters:
        query = f"{query} {' '.join(date_filters)}"
        logger.debug(f"Added date filters: {date_filters}")

    # Add Media Cloud collection sites to query if provided
    if media_cloud_sources:
        media_cloud_sources = media_cloud_sources[:num_mc_sites]  # truncate sites
        mc_filters = [f"site:{site}" for site in media_cloud_sources]
        if mc_filters:
            query = f"{query} {' OR '.join(mc_filters)}"
            logger.debug(f"Added {len(mc_filters)} Media Cloud site filters")

    encoded_query = urllib.parse.quote_plus(query)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bright_data_config.api_key}",
    }

    if news_only:
        news_param = "&tbm=nws"
        logger.debug("Using news only parameter")
    else:
        news_param = ""

    # Convert country name to code if provided
    country_code = None
    if geolocation_country:
        with open(os.path.join(DATA_DIR, "country_to_code.json"), "r") as f:
            country_name_to_code = json.load(f)
        country_code = country_name_to_code.get(geolocation_country)
        assert country_code, f"Could not find country code for '{geolocation_country}'"
        logger.debug(f"Found geolocation country code: {country_code}")
    country_param = f"&gl={country_code}" if country_code else ""

    all_results = []

    for request_num in range(results_pages_per_query):
        logger.debug(f"Making request {request_num + 1}/{results_pages_per_query}")
        # Calculate start parameter for pagination
        start = request_num * 20

        data = {
            "zone": bright_data_config.zone,
            "url": f"https://www.google.com/search?q={encoded_query}&start={start}&brd_json=1&num=20{news_param}{country_param}",
            "format": "raw",
        }

        response = requests.post(
            bright_data_config.base_url, headers=headers, json=data
        )
        response.raise_for_status()
        results = response.json()
        logger.debug(results)
        simplified_results = []

        # Get the appropriate results array based on news_only
        result_items = (
            results.get("news", []) if news_only else results.get("organic", [])
        )

        for item in result_items:
            result = {
                "link": item.get("link", ""),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
            }
            # Add source for news results
            if news_only:
                result["source"] = item.get("source", "")
            simplified_results.append(result)
        logger.debug(
            f"Retrieved {len(simplified_results)} results from request {request_num + 1}"
        )
        all_results.extend(simplified_results)

    logger.debug(f"Retrieved {len(all_results)} results in total")
    return all_results


def _process_queries_and_stream_results(
    search_queries: List[str],
    variable_value_combinations: List[Optional[Tuple[str, ...]]],
    date_chunks: List[Dict[str, str]],
    results_pages_per_query: int,
    bright_data_config: BrightDataConfig,
    media_cloud_sources: Optional[List[str]],
    geolocation_country: Optional[str],
    news_only: bool,
    variable_name_with_assigned_countries: Optional[str] = None,
    variable_values_media_cloud_sources: Optional[Dict[str, List[str]]] = None,
    variable_values_geolocation_countries: Optional[Dict[str, str]] = None,
    search_query_variables: Optional[Dict[str, List[str]]] = None,
) -> Generator[Tuple[Optional[Tuple[str, ...]], str, Dict[str, str]], None, None]:
    """
    Process queries and stream results from all date chunks.

    Args:
        search_queries: List of search query strings to process
        variable_value_combinations: List of variable value combinations corresponding to each query
        date_chunks: List of date range dictionaries with 'start' and 'end' keys
        results_pages_per_query: Number of result pages to retrieve per query
        bright_data_config: Configuration for Bright Data API
        media_cloud_sources: Optional list of Media Cloud source URLs to filter by
        geolocation_country: Optional country code for geolocation filtering
        news_only: Whether to retrieve only news results
        variable_name_with_assigned_countries: Name of the variable whose values we are assigning countries to
        variable_values_media_cloud_sources: Dictionary mapping variable values to lists of Media Cloud sources
        variable_values_geolocation_countries: Dictionary mapping variable values to geolocation countries
        search_query_variables: Dictionary mapping variable names to possible values

    Yields:
        Tuple containing:
            - variable_value_combo: The variable value combination for this query (or None)
            - query: The search query that produced this result
            - result: Dictionary containing the search result (link, title, description, etc.)
    """
    seen_urls = set()

    for query, variable_value_combo in zip(search_queries, variable_value_combinations):
        logger.debug(
            f"Processing query: {query}, variable value combo: {variable_value_combo}"
        )

        # Determine the appropriate Media Cloud sources and geolocation country for this variable value combination
        current_media_cloud_sources = media_cloud_sources
        current_geolocation_country = geolocation_country

        if variable_name_with_assigned_countries and variable_value_combo:
            # Get the variable value that corresponds to the variable_name_with_assigned_countries
            variable_value = _get_variable_value_for_country_assignment(
                variable_value_combo,
                variable_name_with_assigned_countries,
                search_query_variables,
            )

            if variable_value:
                if (
                    variable_values_media_cloud_sources
                    and variable_value in variable_values_media_cloud_sources
                ):
                    current_media_cloud_sources = variable_values_media_cloud_sources[
                        variable_value
                    ]
                    logger.debug(
                        f"Using Media Cloud sources for variable value '{variable_value}': {len(current_media_cloud_sources)} sources"
                    )

                if (
                    variable_values_geolocation_countries
                    and variable_value in variable_values_geolocation_countries
                ):
                    current_geolocation_country = variable_values_geolocation_countries[
                        variable_value
                    ]
                    logger.debug(
                        f"Using geolocation country for variable value '{variable_value}': {current_geolocation_country}"
                    )

        # Process each date chunk and stream results
        yield from _stream_date_chunks(
            query,
            variable_value_combo,
            date_chunks,
            results_pages_per_query,
            bright_data_config,
            current_media_cloud_sources,
            current_geolocation_country,
            news_only,
            seen_urls,
        )


def _stream_date_chunks(
    query: str,
    variable_value_combo: Optional[Tuple[str, ...]],
    date_chunks: List[Dict[str, str]],
    results_pages_per_query: int,
    bright_data_config: BrightDataConfig,
    media_cloud_sources: Optional[List[str]],
    geolocation_country: Optional[str],
    news_only: bool,
    seen_urls: set,
) -> Generator[Tuple[Optional[Tuple[str, ...]], str, Dict[str, str]], None, None]:
    """
    Stream results from all date chunks for a single query.

    Args:
        query: Search query string to process
        variable_value_combo: Variable value combination for this query (or None)
        date_chunks: List of date range dictionaries with 'start' and 'end' keys
        results_pages_per_query: Number of result pages to retrieve per query
        bright_data_config: Configuration for Bright Data API
        media_cloud_sources: Optional list of Media Cloud source URLs to filter by
        geolocation_country: Optional country code for geolocation filtering
        news_only: Whether to retrieve only news results
        seen_urls: Set of URLs already processed to avoid duplicates

    Yields:
        Tuple containing:
            - variable_value_combo: The variable value combination for this query (or None)
            - query: The search query that produced this result
            - result: Dictionary containing the search result (link, title, description, etc.)
    """
    for chunk in date_chunks:
        logger.debug(f"Processing date chunk: {chunk['start']} to {chunk['end']}")

        # Stream results from this date chunk
        yield from _stream_bright_data_results(
            query,
            variable_value_combo,
            results_pages_per_query,
            bright_data_config,
            chunk["start"],
            chunk["end"],
            media_cloud_sources,
            geolocation_country,
            news_only,
            seen_urls,
        )


def _stream_bright_data_results(
    query: str,
    variable_value_combo: Optional[Tuple[str, ...]],
    results_pages_per_query: int,
    bright_data_config: BrightDataConfig,
    start_date: Optional[str],
    end_date: Optional[str],
    media_cloud_sources: Optional[List[str]],
    geolocation_country: Optional[str],
    news_only: bool,
    seen_urls: set,
    num_mc_sites: int = 50,
) -> Generator[Tuple[Optional[Tuple[str, ...]], str, Dict[str, str]], None, None]:
    """
    Stream search results from Bright Data API for a given query.

    Args:
        query: Search query string
        variable_value_combo: Variable value combination for this query (or None)
        results_pages_per_query: Number of result pages to retrieve
        bright_data_config: Configuration for Bright Data API
        start_date: Start date for search filtering (YYYY-MM-DD format)
        end_date: End date for search filtering (YYYY-MM-DD format)
        media_cloud_sources: Optional list of Media Cloud source URLs to filter by
        geolocation_country: Optional country name for geolocation filtering
        news_only: Whether to retrieve only news results
        seen_urls: Set of URLs already processed to avoid duplicates
        num_mc_sites: Maximum number of Media Cloud sites to include in query

    Yields:
        Tuple containing:
            - variable_value_combo: The variable value combination for this query (or None)
            - query: The search query that produced this result
            - result: Dictionary containing the search result (link, title, description, etc.)
    """
    # Build query with date filters
    date_filters = []
    if start_date:
        date_filters.append(f"after:{start_date}")
    if end_date:
        date_filters.append(f"before:{end_date}")
    if date_filters:
        query = f"{query} {' '.join(date_filters)}"
        logger.debug(f"Added date filters: {date_filters}")

    # Add Media Cloud collection sites to query if provided
    if media_cloud_sources:
        media_cloud_sources = media_cloud_sources[:num_mc_sites]  # truncate sites
        mc_filters = [f"site:{site}" for site in media_cloud_sources]
        if mc_filters:
            query = f"{query} {' OR '.join(mc_filters)}"
            logger.debug(f"Added {len(mc_filters)} Media Cloud site filters")

    encoded_query = urllib.parse.quote_plus(query)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bright_data_config.api_key}",
    }

    if news_only:
        news_param = "&tbm=nws"
        logger.debug("Using news only parameter")
    else:
        news_param = ""

    # Convert country name to code if provided
    country_code = None
    if geolocation_country:
        with open(os.path.join(DATA_DIR, "country_to_code.json"), "r") as f:
            country_name_to_code = json.load(f)
        country_code = country_name_to_code.get(geolocation_country)
        assert country_code, f"Could not find country code for '{geolocation_country}'"
        logger.debug(f"Found geolocation country code: {country_code}")
    country_param = f"&gl={country_code}" if country_code else ""

    for request_num in range(results_pages_per_query):
        logger.debug(f"Making request {request_num + 1}/{results_pages_per_query}")
        # Calculate start parameter for pagination
        start = request_num * 20

        data = {
            "zone": bright_data_config.zone,
            "url": f"https://www.google.com/search?q={encoded_query}&start={start}&brd_json=1&num=20{news_param}{country_param}",
            "format": "raw",
        }

        response = requests.post(
            bright_data_config.base_url, headers=headers, json=data
        )
        response.raise_for_status()
        results = response.json()
        logger.debug(results)

        # Get the appropriate results array based on news_only
        result_items = (
            results.get("news", []) if news_only else results.get("organic", [])
        )

        for item in result_items:
            result = {
                "link": item.get("link", ""),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
            }
            # Add source for news results
            if news_only:
                result["source"] = item.get("source", "")

            # Only yield if we haven't seen this URL before
            if result["link"] not in seen_urls:
                seen_urls.add(result["link"])
                yield (variable_value_combo, query, result)

        logger.debug(
            f"Retrieved and yielded {len(result_items)} results from request {request_num + 1}"
        )


def _expand_query_templates(
    templates: List[str],
    variables: Dict[str, List[str]],
) -> Tuple[List[str], List[Optional[Tuple[str, ...]]]]:
    """
    Expand search query templates by replacing variable placeholders with all possible combinations of values.

    Args:
        templates: List of search query templates containing variable placeholders
        variables: Dictionary mapping variable names to lists of possible values

    Returns:
        Tuple containing:
            - List of expanded query strings with variables replaced
            - List of variable value combinations corresponding to each expanded query
    """

    if not variables:
        return templates, [None] * len(templates)

    normalized_variable_names = {
        k.lower().replace(" ", "_"): v for k, v in variables.items()
    }

    expanded_queries = []
    variable_value_combinations = []

    for template in templates:
        # Find all variable placeholders in the template
        placeholders = set()
        for var_name in normalized_variable_names.keys():
            if f"{{{var_name}}}" in template.lower():
                placeholders.add(var_name)

        if not placeholders:
            # If no placeholders found, use template as is
            expanded_queries.append(template)
            variable_value_combinations.append(None)
            continue

        # Get all possible combinations of values for the found placeholders
        var_names = list(placeholders)
        var_values = [normalized_variable_names[name] for name in var_names]
        combinations = list(itertools.product(*var_values))

        # Replace placeholders with each combination of values
        for combo in combinations:
            query = template
            for var_name, value in zip(var_names, combo):
                query = query.replace(f"{{{var_name}}}", value)
            expanded_queries.append(query)
            variable_value_combinations.append(tuple(combo))
    return expanded_queries, variable_value_combinations


def _get_date_chunks(start_date: str, end_date: str) -> List[Dict[str, str]]:
    """
    Split date range into chunks of maximum 1 year each, with equal sizes.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        List of dictionaries, each containing 'start' and 'end' date keys
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # Calculate total days in range
    total_days = (end - start).days + 1

    # Calculate number of chunks needed (each chunk will be at most 1 year)
    max_days_per_chunk = 366
    num_chunks = max(1, (total_days + max_days_per_chunk - 1) // max_days_per_chunk)

    # Calculate days per chunk (equal size)
    days_per_chunk = total_days // num_chunks

    chunks = []
    current_start = start

    for i in range(num_chunks):
        # For the last chunk, use the actual end date
        if i == num_chunks - 1:
            chunk_end = end
        else:
            chunk_end = current_start + timedelta(days=days_per_chunk - 1)

        chunks.append(
            {
                "start": current_start.strftime("%Y-%m-%d"),
                "end": chunk_end.strftime("%Y-%m-%d"),
            }
        )

        # Move to next chunk
        current_start = chunk_end + timedelta(days=1)

    return chunks


def get_media_cloud_sources(collection: str) -> List[str]:
    """
    Get Media Cloud sources for a given collection.

    Args:
        collection: Country name to get Media Cloud sources for

    Returns:
        List of Media Cloud source identifiers
    """
    sources_path = os.path.join(DATA_DIR, "country_to_mc_sources.json")

    with open(sources_path, "r") as f:
        sources = json.load(f)

    return sources[collection]


def rerank_results_jina_api(
    queries: List[str], documents: List[str], jina_config: JinaConfig
) -> List[Dict[str, str]]:
    """
    Rerank documents based on their relevance to queries using the Jina API.

    Args:
        queries (List[str]): List of search queries.
        documents (List[str]): List of document texts to rerank.

    Returns:
        List[Dict[str, str]]: List of reranked documents with query, text, and score.
                                Each dict contains:
                                - "query": The search query
                                - "text": The document text
                                - "score": The relevance score
    """
    if not documents:
        return []

    assert len(queries) == len(
        documents
    ), "Queries and documents must have the same length"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {jina_config.api_key}",
    }

    # Group documents by query
    query_document_groups = {}
    for query, document in zip(queries, documents):
        if query not in query_document_groups:
            query_document_groups[query] = []
        query_document_groups[query].append(document)

    rerank_results = []
    for query, documents_for_query in query_document_groups.items():
        # Rank all documents for this query together
        data = {
            "model": jina_config.model,
            "query": query,
            "top_n": len(documents_for_query),
            "documents": documents_for_query,
            "return_documents": True,
        }
        response = requests.post(jina_config.base_url, headers=headers, json=data)
        response.raise_for_status()
        ranked_docs = response.json()

        # Add results for this query
        for ranked_doc in ranked_docs["results"]:
            rerank_results.append(
                {
                    "query": query,
                    "text": ranked_doc["document"]["text"],
                    "score": ranked_doc["relevance_score"],
                }
            )

    return rerank_results


def get_media_cloud_countries() -> List[str]:
    """
    Get list of countries that have Media Cloud collections.

    Returns:
        List[str]: List of country names that have Media Cloud sources available.
    """
    with open(os.path.join(DATA_DIR, "country_to_mc_sources.json"), "r") as f:
        return list(json.load(f).keys())


def get_geolocation_countries() -> List[str]:
    """
    Get list of countries for which geolocation can be used.

    Returns:
        List[str]: List of country names that have geolocation codes available.
    """
    with open(os.path.join(DATA_DIR, "country_to_code.json"), "r") as f:
        return list(json.load(f).keys())


def get_url_date(url: str) -> str:
    """
    Extract the publication date from a URL using timeout protection.

    Args:
        url (str): The URL to extract the date from

    Returns:
        str: The extracted date string, or None if extraction fails or times out
    """
    date = timeout_function(
        find_date,
        args=(url,),
        kwargs={"extensive_search": True},
        timeout=5,
        default_value=None,
    )
    return date
