from pydantic import BaseModel


class MovieSearchResult(BaseModel):
    tmdb_id: int
    title: str
    poster_url: str | None
    release_date: str | None
