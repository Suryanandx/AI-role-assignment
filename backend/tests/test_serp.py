from unittest.mock import MagicMock, patch

from app.models import SERPResult
from app.services import MockSERPClient, SerpAPIClient, get_serp_client


def test_mock_returns_10_results():
    client = MockSERPClient()
    results = client.get_serp("test query")
    assert len(results) == 10
    for i, r in enumerate(results):
        assert isinstance(r, SERPResult)
        assert r.rank == i + 1
        assert r.url
        assert r.title
        assert r.snippet


def test_results_are_topic_aware():
    client = MockSERPClient()
    results = client.get_serp("best productivity tools")
    combined = " ".join(r.title + " " + r.snippet for r in results).lower()
    assert "productivity" in combined or "tools" in combined


def test_determinism():
    client = MockSERPClient()
    a = client.get_serp("same query")
    b = client.get_serp("same query")
    assert len(a) == len(b) == 10
    for i in range(10):
        assert a[i].rank == b[i].rank
        assert a[i].title == b[i].title
        assert a[i].url == b[i].url
        assert a[i].snippet == b[i].snippet


def test_ranks_unique_and_sequential():
    client = MockSERPClient()
    results = client.get_serp("any topic")
    assert [r.rank for r in results] == list(range(1, 11))


def test_factory_returns_mock():
    client = get_serp_client(use_mock=True)
    results = client.get_serp("factory test")
    assert len(results) == 10
    assert all(isinstance(r, SERPResult) for r in results)


def test_factory_real_without_key_raises():
    import pytest
    with pytest.raises(ValueError, match="SERPAPI_KEY"):
        get_serp_client(use_mock=False)


def test_serpapi_client_maps_organic_results():
    client = SerpAPIClient(api_key="test-key")
    organic = [
        {"position": 1, "title": "First", "link": "https://a.com", "snippet": "Snippet one."},
        {"position": 2, "title": "Second", "link": "https://b.com", "snippet": "Snippet two."},
    ]
    mock_response = MagicMock()
    mock_response.json.return_value = {"organic_results": organic}
    mock_response.raise_for_status = MagicMock()

    with patch("app.services.serp.httpx.Client") as mock_client_cls:
        mock_http = MagicMock()
        mock_http.get.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_http
        mock_client_cls.return_value.__exit__.return_value = False

        results = client.get_serp("test query")

    assert len(results) == 2
    assert results[0].rank == 1 and results[0].title == "First" and results[0].url == "https://a.com"
    assert results[0].snippet == "Snippet one."
    assert results[1].rank == 2 and results[1].title == "Second"
    mock_http.get.assert_called_once()
    call_kw = mock_http.get.call_args
    assert call_kw[1]["params"]["q"] == "test query"
    assert call_kw[1]["params"]["api_key"] == "test-key"


def test_serpapi_client_empty_results():
    client = SerpAPIClient(api_key="test-key")
    mock_response = MagicMock()
    mock_response.json.return_value = {"organic_results": []}
    mock_response.raise_for_status = MagicMock()

    with patch("app.services.serp.httpx.Client") as mock_client_cls:
        mock_http = MagicMock()
        mock_http.get.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_http
        mock_client_cls.return_value.__exit__.return_value = False

        results = client.get_serp("query")

    assert results == []


def test_serpapi_client_sorts_by_rank():
    client = SerpAPIClient(api_key="test-key")
    organic = [
        {"position": 3, "title": "Third", "link": "https://c.com", "snippet": "C"},
        {"position": 1, "title": "First", "link": "https://a.com", "snippet": "A"},
    ]
    mock_response = MagicMock()
    mock_response.json.return_value = {"organic_results": organic}
    mock_response.raise_for_status = MagicMock()

    with patch("app.services.serp.httpx.Client") as mock_client_cls:
        mock_http = MagicMock()
        mock_http.get.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_http
        mock_client_cls.return_value.__exit__.return_value = False

        results = client.get_serp("query")

    assert [r.rank for r in results] == [1, 3]
    assert results[0].title == "First" and results[1].title == "Third"


def test_factory_returns_serpapi_client_when_key_set():
    from types import SimpleNamespace
    settings = SimpleNamespace(serp_use_mock=False, serp_provider="serpapi", serpapi_key="my-key")
    client = get_serp_client(use_mock=False, settings=settings)
    assert isinstance(client, SerpAPIClient)
    assert client.api_key == "my-key"
