import httpx
import pytest

from app.services.catalog import CatalogUnavailableError, MovieResult, search_movies


def _fake_get(response: httpx.Response | None = None, exc: Exception | None = None):
    def fake_get(url, params=None, timeout=None):
        if exc is not None:
            raise exc
        return response

    return fake_get


def _tmdb_response(payload: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code, json=payload, request=httpx.Request("GET", "http://testserver")
    )


class TestSearchMovies:
    def test_search_movies_maps_tmdb_results_to_movie_results(self, monkeypatch):
        payload = {
            "results": [
                {
                    "id": 603,
                    "title": "The Matrix",
                    "poster_path": "/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg",
                    "release_date": "1999-03-30",
                }
            ]
        }
        monkeypatch.setattr(
            "app.services.catalog.httpx.get", _fake_get(_tmdb_response(payload))
        )

        results = search_movies("matrix")

        assert results == [
            MovieResult(
                tmdb_id=603,
                title="The Matrix",
                poster_url=(
                    "https://image.tmdb.org/t/p/w500"
                    "/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg"
                ),
                release_date="1999-03-30",
            )
        ]

    def test_search_movies_with_null_poster_path_returns_none_poster_url(
        self, monkeypatch
    ):
        payload = {
            "results": [
                {
                    "id": 1,
                    "title": "No Poster Movie",
                    "poster_path": None,
                    "release_date": "2020-01-01",
                }
            ]
        }
        monkeypatch.setattr(
            "app.services.catalog.httpx.get", _fake_get(_tmdb_response(payload))
        )

        results = search_movies("no poster")

        assert results[0].poster_url is None

    def test_search_movies_on_timeout_raises_catalog_unavailable_error(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.catalog.httpx.get",
            _fake_get(exc=httpx.TimeoutException("timed out")),
        )

        with pytest.raises(CatalogUnavailableError):
            search_movies("anything")

    def test_search_movies_on_http_error_status_raises_catalog_unavailable_error(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.catalog.httpx.get",
            _fake_get(_tmdb_response({}, status_code=500)),
        )

        with pytest.raises(CatalogUnavailableError):
            search_movies("anything")
