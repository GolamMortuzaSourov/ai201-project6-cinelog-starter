"""
tests/test_watchlist.py — CineLog

Tests for the watchlist service. Follows the same pattern as
tests/test_collection.py: an in-memory app fixture plus sample_user
and sample_film fixtures, covering the happy path, duplicate handling,
and the nonexistent-film case.
"""

import pytest
from app import create_app, db
from models import User, Film, WatchlistEntry
from services.watchlist_service import (
    add_to_watchlist,
    get_watchlist,
    AlreadyInWatchlistError,
)
from services.collection_service import FilmNotFoundError


@pytest.fixture
def app():
    """Create an isolated test app with an in-memory database."""
    app = create_app(config={
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def sample_user(app):
    """A user to use in tests."""
    with app.app_context():
        user = User(username="testuser", email="test@example.com")
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture
def sample_film(app):
    """A film to use in tests."""
    with app.app_context():
        film = Film(title="Paddington 2", year=2017, genre="Comedy")
        db.session.add(film)
        db.session.commit()
        return film.id


# ── Basic add ───────────────────────────────────────────────────────────────

def test_add_to_watchlist_creates_entry(app, sample_user, sample_film):
    """
    Adding a valid film should create a WatchlistEntry in the database.
    """
    with app.app_context():
        entry = add_to_watchlist(user_id=sample_user, film_id=sample_film)

        assert entry is not None
        assert entry.user_id == sample_user
        assert entry.film_id == sample_film

        # Verify it persisted
        in_db = WatchlistEntry.query.filter_by(
            user_id=sample_user, film_id=sample_film
        ).first()
        assert in_db is not None


# ── Deduplication ────────────────────────────────────────────────────────────

def test_add_to_watchlist_duplicate_raises(app, sample_user, sample_film):
    """
    Adding the same film twice should raise AlreadyInWatchlistError,
    not silently create a duplicate entry.
    """
    with app.app_context():
        add_to_watchlist(user_id=sample_user, film_id=sample_film)

        with pytest.raises(AlreadyInWatchlistError):
            add_to_watchlist(user_id=sample_user, film_id=sample_film)

        # Confirm only one entry exists
        count = WatchlistEntry.query.filter_by(
            user_id=sample_user, film_id=sample_film
        ).count()
        assert count == 1


# ── Nonexistent film ─────────────────────────────────────────────────────────

def test_add_to_watchlist_nonexistent_film_raises(app, sample_user):
    """
    Adding a film_id that doesn't exist in the database should raise
    FilmNotFoundError, not a database integrity error.
    """
    with app.app_context():
        fake_film_id = "00000000-0000-0000-0000-000000000000"

        with pytest.raises(FilmNotFoundError):
            add_to_watchlist(user_id=sample_user, film_id=fake_film_id)


# ── get_watchlist read path ──────────────────────────────────────────────────

def test_get_watchlist_returns_saved_films(app, sample_user, sample_film):
    """
    get_watchlist() should return the films a user has saved, with the
    watchlist metadata (date_added, public) attached. This exercises the
    WatchlistEntry -> Film relationship used to build each result dict.
    """
    with app.app_context():
        add_to_watchlist(user_id=sample_user, film_id=sample_film)

        watchlist = get_watchlist(sample_user)

        assert len(watchlist) == 1
        assert watchlist[0]["title"] == "Paddington 2"
        assert watchlist[0]["public"] is False  # private by default
        assert "date_added" in watchlist[0]


# ── Visibility toggle ────────────────────────────────────────────────────────

def test_add_to_watchlist_public_flag(app, sample_user, sample_film):
    """
    Entries default to private, but a caller can opt in to public visibility
    by passing public=True.
    """
    with app.app_context():
        default_entry = add_to_watchlist(user_id=sample_user, film_id=sample_film)
        assert default_entry.public is False

    with app.app_context():
        # A different user can share the same film publicly.
        other = User(username="sharer", email="share@example.com")
        db.session.add(other)
        db.session.commit()
        public_entry = add_to_watchlist(
            user_id=other.id, film_id=sample_film, public=True
        )
        assert public_entry.public is True


# ── Sort order ───────────────────────────────────────────────────────────────

def test_get_watchlist_sort_options(app, sample_user):
    """
    get_watchlist() defaults to date_added (newest first) and supports
    sort="title" for alphabetical ordering.
    """
    with app.app_context():
        from datetime import datetime, timezone, timedelta

        # "Zodiac" added later than "Amelie"
        amelie = Film(title="Amelie", year=2001)
        zodiac = Film(title="Zodiac", year=2007)
        db.session.add_all([amelie, zodiac])
        db.session.commit()

        earlier = datetime.now(timezone.utc) - timedelta(days=1)
        later = datetime.now(timezone.utc)
        db.session.add_all([
            WatchlistEntry(user_id=sample_user, film_id=amelie.id, date_added=earlier),
            WatchlistEntry(user_id=sample_user, film_id=zodiac.id, date_added=later),
        ])
        db.session.commit()

        # Default: newest first → Zodiac before Amelie
        default_titles = [f["title"] for f in get_watchlist(sample_user)]
        assert default_titles == ["Zodiac", "Amelie"]

        # Alphabetical → Amelie before Zodiac
        title_titles = [f["title"] for f in get_watchlist(sample_user, sort="title")]
        assert title_titles == ["Amelie", "Zodiac"]
