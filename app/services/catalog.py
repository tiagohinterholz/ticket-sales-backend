from dataclasses import dataclass

import httpx

from app.core.config import settings

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
REQUEST_TIMEOUT_SECONDS = 5.0


class CatalogUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class MovieResult:
    tmdb_id: int
    title: str
    poster_url: str | None
    release_date: str | None


def search_movies(query: str) -> list[MovieResult]:
    try:
        response = httpx.get(
            f"{TMDB_BASE_URL}/search/movie",
            params={"query": query},
            headers={"Authorization": f"Bearer {settings.TMDB_API_KEY}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise CatalogUnavailableError("TMDb catalog is unavailable") from exc

    payload = response.json()
    return [_to_movie_result(item) for item in payload.get("results", [])]


def _to_movie_result(item: dict) -> MovieResult:
    poster_path = item.get("poster_path")
    return MovieResult(
        tmdb_id=item["id"],
        title=item["title"],
        poster_url=f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None,
        release_date=item.get("release_date") or None,
    )
