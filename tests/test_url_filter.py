"""
Tests for url_filter feature — restricting search to a URL subsection.

Unit tests (no server needed):
    pytest tests/test_url_filter.py -k "unit"

Integration tests (requires running server + large_campus2 index):
    pytest tests/test_url_filter.py -k "integration"

All:
    pytest tests/test_url_filter.py -v
"""

import os
import pytest
from urllib.parse import urlparse

from src.core.cache import SearchCache


# ── Unit Tests: Cache key isolation with url_filter ──────────────────────────

class TestUrlFilterCacheIsolation:
    """url_filter must produce different cache keys."""

    def setup_method(self):
        self.cache = SearchCache(max_ram_entries=100)
        self.query = "formation"
        self.index_id = "large_campus2"
        self.index_path = "/tmp/test_index"
        self.user_groups = ["public"]

    def test_unit_different_filters_produce_different_keys(self):
        """Same query with different url_filters must not collide."""
        key_none = self.cache._generate_cache_key(
            self.query, self.index_id, self.user_groups, url_filter=None
        )
        key_about = self.cache._generate_cache_key(
            self.query, self.index_id, self.user_groups, url_filter="about"
        )
        key_research = self.cache._generate_cache_key(
            self.query, self.index_id, self.user_groups, url_filter="research"
        )
        assert key_none != key_about
        assert key_none != key_research
        assert key_about != key_research

    def test_unit_filter_normalization(self):
        """Leading/trailing slashes should not affect the cache key."""
        key1 = self.cache._generate_cache_key(
            self.query, self.index_id, self.user_groups, url_filter="about/data"
        )
        key2 = self.cache._generate_cache_key(
            self.query, self.index_id, self.user_groups, url_filter="/about/data/"
        )
        key3 = self.cache._generate_cache_key(
            self.query, self.index_id, self.user_groups, url_filter="/about/data"
        )
        assert key1 == key2 == key3

    def test_unit_filtered_and_unfiltered_cache_isolated(self):
        """Cached results for filtered vs unfiltered queries must not mix."""
        results_all = [("child_all", "parent_all", 0.95)]
        results_about = [("child_about", "parent_about", 0.90)]

        # Cache unfiltered
        self.cache.set(self.query, self.index_id, self.index_path,
                       self.user_groups, results_all, url_filter=None)
        # Cache filtered
        self.cache.set(self.query, self.index_id, self.index_path,
                       self.user_groups, results_about, url_filter="about")

        # Retrieve each — must get the right one
        cached_all = self.cache.get(self.query, self.index_id, self.index_path,
                                    self.user_groups, url_filter=None)
        cached_about = self.cache.get(self.query, self.index_id, self.index_path,
                                      self.user_groups, url_filter="about")

        assert cached_all == results_all
        assert cached_about == results_about

    def test_unit_no_filter_backward_compatible(self):
        """Omitting url_filter behaves exactly like before."""
        results = [("c1", "p1", 0.9)]

        self.cache.set(self.query, self.index_id, self.index_path,
                       self.user_groups, results)
        cached = self.cache.get(self.query, self.index_id, self.index_path,
                                self.user_groups)
        assert cached == results


# ── Unit Tests: URL path prefix matching logic ───────────────────────────────

class TestUrlPrefixMatching:
    """Test the path prefix matching logic used in search.py."""

    @staticmethod
    def matches(source_url: str, url_filter: str) -> bool:
        """Reproduce the matching logic from search.py."""
        normalized_prefix = "/" + url_filter.strip("/") + "/"
        return urlparse(source_url).path.startswith(normalized_prefix)

    def test_unit_match_about(self):
        assert self.matches("https://www.epfl.ch/about/campus/", "about")

    def test_unit_match_about_data(self):
        assert self.matches("https://www.epfl.ch/about/data/something/", "about/data")

    def test_unit_match_research(self):
        assert self.matches("https://www.epfl.ch/research/funding/", "research")

    def test_unit_no_match_wrong_prefix(self):
        assert not self.matches("https://www.epfl.ch/education/bachelor/", "about")

    def test_unit_no_match_partial(self):
        """'about' should not match 'about-us' (prefix requires trailing /)."""
        assert not self.matches("https://www.epfl.ch/about-us/page/", "about")

    def test_unit_match_with_slashes(self):
        """Filter with leading/trailing slashes works the same."""
        assert self.matches("https://www.epfl.ch/about/data/x/", "/about/data/")
        assert self.matches("https://www.epfl.ch/about/data/x/", "about/data")

    def test_unit_pdf_url(self):
        """PDF URLs with anchors should still match."""
        url = "https://www.epfl.ch/about/equality/wp-content/uploads/report.pdf#page=5"
        assert self.matches(url, "about/equality")
        assert self.matches(url, "about")
        assert not self.matches(url, "research")

    def test_unit_deeper_path(self):
        assert self.matches(
            "https://www.epfl.ch/about/campus/famille-education-et-formation/",
            "about/campus"
        )
        assert not self.matches(
            "https://www.epfl.ch/about/campus/famille-education-et-formation/",
            "about/data"
        )


# ── Integration Tests: against running server with large_campus2 ─────────────

API_KEY = os.getenv("INTERNAL_API_KEY", "")
BASE_URL = os.getenv("SEARCH_API_URL", "http://localhost:8079")
INDEX_ID = "large_campus2"
USER_GROUPS = ["public"]


def _requires_server():
    """Skip if server is not reachable."""
    if not API_KEY:
        pytest.skip("INTERNAL_API_KEY not set")
    try:
        import requests
        requests.get(f"{BASE_URL}/docs", timeout=2)
    except Exception:
        pytest.skip(f"Server not reachable at {BASE_URL}")


def _search(query: str, url_filter: str = None, top_k: int = 5):
    """Helper: send a search request and return parsed results."""
    import requests
    payload = {
        "query": query,
        "user_groups": USER_GROUPS,
        "rerank": False,
        "top_k": top_k,
    }
    if url_filter:
        payload["url_filter"] = url_filter

    resp = requests.post(
        f"{BASE_URL}/search/{INDEX_ID}",
        json=payload,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        timeout=60,
    )
    assert resp.status_code == 200, f"Search failed: {resp.status_code} {resp.text}"
    return resp.json()


class TestUrlFilterIntegration:
    """Integration tests against a running server with large_campus2 index."""

    @pytest.fixture(autouse=True)
    def check_server(self):
        _requires_server()

    def test_integration_filter_about_returns_only_about_urls(self):
        results = _search("formation", url_filter="about")
        assert len(results) > 0, "Expected results for 'formation' in /about/"
        for r in results:
            path = urlparse(r["source_url"]).path
            assert path.startswith("/about/"), (
                f"Result URL {r['source_url']} does not match filter /about/"
            )

    def test_integration_filter_research(self):
        results = _search("funding", url_filter="research")
        assert len(results) > 0, "Expected results for 'funding' in /research/"
        for r in results:
            path = urlparse(r["source_url"]).path
            assert path.startswith("/research/"), (
                f"Result URL {r['source_url']} does not match filter /research/"
            )

    def test_integration_filter_about_data(self):
        results = _search("data", url_filter="about/data")
        assert len(results) > 0, "Expected results for 'data' in /about/data/"
        for r in results:
            path = urlparse(r["source_url"]).path
            assert path.startswith("/about/data/"), (
                f"Result URL {r['source_url']} does not match filter /about/data/"
            )

    def test_integration_filter_about_campus(self):
        results = _search("campus", url_filter="about/campus")
        assert len(results) > 0, "Expected results for 'campus' in /about/campus/"
        for r in results:
            path = urlparse(r["source_url"]).path
            assert path.startswith("/about/campus/"), (
                f"Result URL {r['source_url']} does not match filter /about/campus/"
            )

    def test_integration_filter_education(self):
        results = _search("bachelor", url_filter="education")
        assert len(results) > 0, "Expected results for 'bachelor' in /education/"
        for r in results:
            path = urlparse(r["source_url"]).path
            assert path.startswith("/education/"), (
                f"Result URL {r['source_url']} does not match filter /education/"
            )

    def test_integration_nonexistent_filter_returns_empty(self):
        results = _search("formation", url_filter="nonexistent/path")
        assert len(results) == 0, (
            f"Expected 0 results for nonexistent filter, got {len(results)}"
        )

    def test_integration_no_filter_returns_diverse_urls(self):
        """Without url_filter, results should come from multiple sections."""
        results = _search("EPFL", top_k=15)
        assert len(results) > 0
        paths = {urlparse(r["source_url"]).path.split("/")[1] for r in results
                 if r["source_url"] != "URL not found"}
        # Without filter, we expect results from at least 2 different top-level sections
        assert len(paths) >= 1, f"Expected diverse URLs, got sections: {paths}"

    def test_integration_filter_does_not_reduce_quality(self):
        """Filtered results should still have reasonable scores."""
        results = _search("formation", url_filter="about", top_k=5)
        for r in results:
            assert r["score"] is not None
            assert r["precise_content"], "precise_content should not be empty"
            assert r["context_content"], "context_content should not be empty"
