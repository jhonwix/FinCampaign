"""
RAG retrieval layer using Vertex AI Search (Discovery Engine).

The Discovery Engine SDK is synchronous. All public functions in this module
are async and wrap the synchronous SDK calls in run_in_executor to avoid
blocking the FastAPI event loop.
"""

import asyncio
from functools import partial

from google.cloud import discoveryengine_v1 as discoveryengine
from google.oauth2 import service_account

from config import settings


def _get_credentials():
    """Load service account credentials from the path in config."""
    try:
        return service_account.Credentials.from_service_account_file(
            settings.service_account_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    except Exception:
        return None  # Fall back to ADC if file not found


# ── Singleton client — created once, reused across all RAG calls (A2) ────────
_search_client: discoveryengine.SearchServiceClient | None = None


def _get_search_client() -> discoveryengine.SearchServiceClient:
    """Return a module-level singleton SearchServiceClient (thread-safe init)."""
    global _search_client
    if _search_client is None:
        _search_client = discoveryengine.SearchServiceClient(
            credentials=_get_credentials()
        )
    return _search_client


# ── In-process RAG cache — deduplicates identical queries within a batch (A1) ─
# Key: (query, num_results, datastore_id). Cleared at the start of each campaign run.
# For 100 customers: reduces ~600 RAG calls to ~25 unique queries per batch.
_rag_cache: dict[tuple, str] = {}


def clear_rag_cache() -> None:
    """Clear the RAG cache. Call at the start of each campaign batch run."""
    global _rag_cache
    _rag_cache = {}
    print(f"[RAG] Cache cleared")


def _sync_search(query: str, serving_config: str, num_results: int) -> list[str]:
    """
    Blocking Vertex AI Search call. Intended to be called via run_in_executor.
    Returns a list of extracted text snippets from the search results.
    """
    client = _get_search_client()

    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=query,
        page_size=num_results,
        content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
            snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                return_snippet=True,
                max_snippet_count=3,
            ),
            summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
                summary_result_count=num_results,
                include_citations=False,
            ),
        ),
    )

    response = client.search(request=request)
    snippets: list[str] = []

    for result in response.results:
        doc = result.document
        if doc.derived_struct_data:
            for snippet_item in doc.derived_struct_data.get("snippets", []):
                text = snippet_item.get("snippet", "")
                if text:
                    link = doc.derived_struct_data.get("link", "")
                    prefix = f"[Source: {link}]\n" if link else ""
                    snippets.append(f"{prefix}{text}")

    return snippets


async def retrieve_context(
    query: str,
    num_results: int = 3,
    datastore_id: str | None = None,
    use_cache: bool = True,
) -> str:
    """
    Async interface for Vertex AI Search retrieval.

    Args:
        query: Natural language query for policy retrieval.
        num_results: Number of document chunks to retrieve.
        datastore_id: Override datastore (uses settings default if None).

    Returns:
        Formatted context string for prompt injection, or a fallback message
        if the search fails or returns no results.
    """
    if datastore_id:
        serving_config = (
            f"projects/{settings.google_cloud_project}"
            f"/locations/global/collections/default_collection"
            f"/dataStores/{datastore_id}/servingConfigs/default_config"
        )
    else:
        serving_config = settings.serving_config

    # ── Cache lookup (A1) ───────────────────────────────────────────────────
    cache_key = (query, num_results, datastore_id)
    if use_cache and cache_key in _rag_cache:
        return _rag_cache[cache_key]

    loop = asyncio.get_running_loop()
    try:
        snippets = await loop.run_in_executor(
            None,
            partial(_sync_search, query, serving_config, num_results),
        )
    except Exception as e:
        print(f"[RAG] Search failed for query '{query[:60]}...': {e}")
        return "[No RAG context available — using base model knowledge]"

    if not snippets:
        return "[No relevant policies found for this query]"

    body = "\n\n".join(f"- {s}" for s in snippets)
    result = (
        "--- Relevant Policy Context (from official documents) ---\n"
        f"{body}\n"
        "---"
    )

    # ── Cache store ─────────────────────────────────────────────────────────
    if use_cache:
        _rag_cache[cache_key] = result

    return result


async def retrieve_multi_context(
    queries: dict[str, str],
    num_results: int = 2,
) -> dict[str, str]:
    """
    Retrieve context for multiple queries concurrently.

    Args:
        queries: Mapping of label -> query string.
                 e.g. {"risk": "DTI scoring rules...", "catalog": "product rates..."}

    Returns:
        Mapping of label -> formatted context string.
    """
    tasks = [retrieve_context(q, num_results) for q in queries.values()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        key: (result if not isinstance(result, Exception) else "[RAG error]")
        for key, result in zip(queries.keys(), results)
    }
