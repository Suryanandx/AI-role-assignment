from app.models import SERPResult
from app.services import MockSERPClient, get_serp_client


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


def test_factory_real_raises():
    import pytest
    with pytest.raises(NotImplementedError):
        get_serp_client(use_mock=False)
