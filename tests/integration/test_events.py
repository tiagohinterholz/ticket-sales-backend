import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.seat import Seat, SeatStatus
from app.models.user import Role, User
from app.services.catalog import CatalogUnavailableError, MovieResult
from tests.integration.factories import auth_headers as _auth_headers
from tests.integration.factories import make_user as _make_user


def _movie(title: str = "The Matrix", tmdb_id: int | None = None) -> MovieResult:
    return MovieResult(
        tmdb_id=tmdb_id or uuid.uuid4().int % 1_000_000,
        title=title,
        poster_url="https://image.tmdb.org/t/p/w500/matrix.jpg",
        release_date="1999-03-30",
    )


def _event_payload(**overrides) -> dict:
    payload = {
        "movie_query": "matrix",
        "venue": "Cinema Central",
        "starts_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        "rows": 2,
        "seats_per_row": 3,
        "price_cents": 2500,
    }
    payload.update(overrides)
    return payload


def _mock_search_movies(monkeypatch, movies: list[MovieResult] | None = None):
    result = movies if movies is not None else [_movie()]

    def fake_search_movies(query: str) -> list[MovieResult]:
        return result

    monkeypatch.setattr("app.api.v1.events.search_movies", fake_search_movies)
    monkeypatch.setattr("app.services.event.search_movies", fake_search_movies)


def _mock_search_movies_unavailable(monkeypatch):
    def fake_search_movies(query: str) -> list[MovieResult]:
        raise CatalogUnavailableError("TMDb is down")

    monkeypatch.setattr("app.api.v1.events.search_movies", fake_search_movies)
    monkeypatch.setattr("app.services.event.search_movies", fake_search_movies)


class TestSearchCatalog:
    def test_search_returns_tmdb_results_for_organizer(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        _mock_search_movies(
            monkeypatch,
            [
                _movie(title="The Matrix", tmdb_id=603),
                _movie(title="The Matrix Reloaded", tmdb_id=604),
            ],
        )

        response = client.get(
            "/events/catalog",
            params={"query": "matrix"},
            headers=_auth_headers(organizer),
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["tmdb_id"] == 603
        assert body[0]["title"] == "The Matrix"
        assert body[1]["tmdb_id"] == 604

    def test_search_when_tmdb_unavailable_returns_502(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        _mock_search_movies_unavailable(monkeypatch)

        response = client.get(
            "/events/catalog",
            params={"query": "matrix"},
            headers=_auth_headers(organizer),
        )

        assert response.status_code == 502

    def test_search_by_customer_returns_403(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        customer = _make_user(db_session, Role.CUSTOMER)
        _mock_search_movies(monkeypatch)

        response = client.get(
            "/events/catalog",
            params={"query": "matrix"},
            headers=_auth_headers(customer),
        )

        assert response.status_code == 403

    def test_search_without_auth_returns_401(self, client: TestClient, monkeypatch):
        _mock_search_movies(monkeypatch)

        response = client.get("/events/catalog", params={"query": "matrix"})

        assert response.status_code == 401


class TestCreateEvent:
    def test_create_event_with_valid_movie_creates_event_and_seat_grid(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        _mock_search_movies(monkeypatch, [_movie(title="The Matrix", tmdb_id=603)])

        response = client.post(
            "/events",
            json=_event_payload(rows=2, seats_per_row=3, price_cents=2500),
            headers=_auth_headers(organizer),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["capacity"] == 6
        assert body["title"] == "The Matrix"
        assert body["tmdb_movie_id"] == 603
        assert body["price_cents"] == 2500

        seats = (
            db_session.execute(
                select(Seat).where(Seat.event_id == uuid.UUID(body["id"]))
            )
            .scalars()
            .all()
        )
        assert len(seats) == 6
        assert all(seat.status == SeatStatus.AVAILABLE for seat in seats)
        assert {seat.row_label for seat in seats} == {"A", "B"}

    def test_create_event_with_past_start_date_returns_422_on_that_field(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        _mock_search_movies(monkeypatch)
        past_date = (datetime.now(UTC) - timedelta(days=1)).isoformat()

        response = client.post(
            "/events",
            json=_event_payload(starts_at=past_date),
            headers=_auth_headers(organizer),
        )

        assert response.status_code == 422
        fields = {tuple(err["loc"]) for err in response.json()["detail"]}
        assert ("body", "starts_at") in fields

    def test_create_event_with_zero_capacity_returns_422_on_that_field(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        _mock_search_movies(monkeypatch)

        response = client.post(
            "/events",
            json=_event_payload(rows=0),
            headers=_auth_headers(organizer),
        )

        assert response.status_code == 422
        fields = {tuple(err["loc"]) for err in response.json()["detail"]}
        assert ("body", "rows") in fields

    def test_create_event_with_negative_price_returns_422_on_that_field(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        _mock_search_movies(monkeypatch)

        response = client.post(
            "/events",
            json=_event_payload(price_cents=-100),
            headers=_auth_headers(organizer),
        )

        assert response.status_code == 422
        fields = {tuple(err["loc"]) for err in response.json()["detail"]}
        assert ("body", "price_cents") in fields

    def test_create_event_when_tmdb_unavailable_returns_502_and_does_not_persist(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        _mock_search_movies_unavailable(monkeypatch)
        unique_venue = f"Venue-{uuid.uuid4()}"

        response = client.post(
            "/events",
            json=_event_payload(venue=unique_venue),
            headers=_auth_headers(organizer),
        )

        assert response.status_code == 502
        persisted = db_session.execute(
            select(Event).where(Event.venue == unique_venue)
        ).scalar_one_or_none()
        assert persisted is None

    def test_create_event_by_gate_staff_returns_403(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        gate_staff = _make_user(db_session, Role.GATE_STAFF)
        _mock_search_movies(monkeypatch)

        response = client.post(
            "/events", json=_event_payload(), headers=_auth_headers(gate_staff)
        )

        assert response.status_code == 403

    def test_create_event_without_auth_returns_401(
        self, client: TestClient, monkeypatch
    ):
        _mock_search_movies(monkeypatch)

        response = client.post("/events", json=_event_payload())

        assert response.status_code == 401

    def test_create_event_with_tmdb_movie_id_selects_that_movie_not_the_first(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        _mock_search_movies(
            monkeypatch,
            [
                _movie(title="The Matrix", tmdb_id=603),
                _movie(title="The Matrix Reloaded", tmdb_id=604),
            ],
        )

        response = client.post(
            "/events",
            json=_event_payload(tmdb_movie_id=604),
            headers=_auth_headers(organizer),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["tmdb_movie_id"] == 604
        assert body["title"] == "The Matrix Reloaded"

    def test_create_event_with_tmdb_movie_id_not_in_results_returns_422(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        _mock_search_movies(monkeypatch, [_movie(title="The Matrix", tmdb_id=603)])

        response = client.post(
            "/events",
            json=_event_payload(tmdb_movie_id=999999),
            headers=_auth_headers(organizer),
        )

        assert response.status_code == 422


class TestListEvents:
    def _create_event(
        self,
        client: TestClient,
        db_session: Session,
        organizer: User,
        monkeypatch,
        **overrides,
    ) -> dict:
        title = overrides.pop("movie_title", "Unique Movie " + str(uuid.uuid4()))
        _mock_search_movies(monkeypatch, [_movie(title=title)])
        response = client.post(
            "/events",
            json=_event_payload(**overrides),
            headers=_auth_headers(organizer),
        )
        assert response.status_code == 201
        return response.json()

    def test_list_events_filters_by_query_text(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        marker = str(uuid.uuid4())
        matching_title = f"Findable {marker}"
        self._create_event(
            client, db_session, organizer, monkeypatch, movie_title=matching_title
        )
        self._create_event(
            client,
            db_session,
            organizer,
            monkeypatch,
            movie_title=f"Other Movie {uuid.uuid4()}",
        )

        response = client.get("/events", params={"q": marker})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == matching_title

    def test_list_events_with_no_match_returns_empty_list_with_metadata(
        self, client: TestClient
    ):
        response = client.get("/events", params={"q": f"nonexistent-{uuid.uuid4()}"})

        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_list_events_filters_by_price_range(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        marker = str(uuid.uuid4())
        cheap_title = f"Cheap {marker}"
        pricey_title = f"Pricey {marker}"
        self._create_event(
            client,
            db_session,
            organizer,
            monkeypatch,
            movie_title=cheap_title,
            price_cents=1000,
        )
        self._create_event(
            client,
            db_session,
            organizer,
            monkeypatch,
            movie_title=pricey_title,
            price_cents=9000,
        )

        response = client.get(
            "/events",
            params={"q": marker, "price_min": 500, "price_max": 2000},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == cheap_title

    def test_list_events_filters_by_date_range(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        marker = str(uuid.uuid4())
        near_title = f"Near {marker}"
        far_title = f"Far {marker}"
        near_date = datetime.now(UTC) + timedelta(days=2)
        far_date = datetime.now(UTC) + timedelta(days=60)
        self._create_event(
            client,
            db_session,
            organizer,
            monkeypatch,
            movie_title=near_title,
            starts_at=near_date.isoformat(),
        )
        self._create_event(
            client,
            db_session,
            organizer,
            monkeypatch,
            movie_title=far_title,
            starts_at=far_date.isoformat(),
        )

        response = client.get(
            "/events",
            params={
                "q": marker,
                "date_from": datetime.now(UTC).isoformat(),
                "date_to": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == near_title


class TestGetEventDetail:
    def test_get_event_detail_returns_seat_map(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        organizer = _make_user(db_session, Role.ORGANIZER)
        _mock_search_movies(monkeypatch, [_movie(title="Detail Movie")])
        create_response = client.post(
            "/events",
            json=_event_payload(rows=2, seats_per_row=2),
            headers=_auth_headers(organizer),
        )
        event_id = create_response.json()["id"]

        response = client.get(f"/events/{event_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == event_id
        assert len(body["seats"]) == 4
        assert all(seat["status"] == "AVAILABLE" for seat in body["seats"])
