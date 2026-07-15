"""
services/watchlist_service.py — CineLog

Business logic for the watchlist feature.
"""

from app import db
from models import Film, WatchlistEntry
from services.collection_service import FilmNotFoundError


class AlreadyInWatchlistError(Exception):
    """Raised when a film is already on the user's watchlist."""
    pass


def add_to_watchlist(user_id, film_id, public=False):
    """
    Add a film to a user's watchlist.

    Args:
        user_id (str): UUID of the user.
        film_id (str): UUID of the film.
        public (bool, optional): Whether the entry is publicly visible.
            Defaults to False (private); callers may pass True to opt in
            to sharing.

    Returns:
        WatchlistEntry: The newly created entry.

    Raises:
        FilmNotFoundError: If film_id does not exist.
        AlreadyInWatchlistError: If the film is already on the user's watchlist.
    """
    film = db.session.get(Film, film_id)
    if film is None:
        raise FilmNotFoundError(f"No film found with id '{film_id}'")

    existing = WatchlistEntry.query.filter_by(
        user_id=user_id, film_id=film_id
    ).first()
    if existing:
        raise AlreadyInWatchlistError(
            f"Film '{film_id}' is already on this user's watchlist"
        )

    entry = WatchlistEntry(user_id=user_id, film_id=film_id, public=public)
    db.session.add(entry)
    db.session.commit()
    return entry


def get_watchlist(user_id, sort="date_added"):
    """
    Return all films on a user's watchlist.

    Args:
        user_id (str): UUID of the user.
        sort (str, optional): Ordering of results. "date_added" (default)
            returns newest first, matching get_collection; "title" returns
            alphabetical by film title.

    Returns:
        list[dict]: List of film dicts with watchlist metadata attached.
    """
    query = WatchlistEntry.query.filter_by(user_id=user_id)
    if sort == "title":
        query = query.join(Film).order_by(Film.title.asc())
    else:  # "date_added" (default) — newest first
        query = query.order_by(WatchlistEntry.date_added.desc())
    entries = query.all()

    result = []
    for entry in entries:
        film_dict = entry.film.to_dict()
        film_dict["date_added"] = entry.date_added.isoformat()
        film_dict["public"] = entry.public
        result.append(film_dict)

    return result
