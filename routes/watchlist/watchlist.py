"""
routes/watchlist.py — CineLog

Endpoints for the watchlist feature.
"""

from flask import Blueprint, jsonify, request
from services.watchlist_service import add_to_watchlist, get_watchlist
from services.collection_service import FilmNotFoundError

watchlist_bp = Blueprint("watchlist", __name__)


@watchlist_bp.route("/<user_id>", methods=["GET"])
def view_watchlist(user_id):
    """
    GET /watchlist/<user_id> — Return the user's watchlist.

    Optional query param: ?sort=date_added (default) | title
    """
    sort = request.args.get("sort", "date_added")
    films = get_watchlist(user_id, sort=sort)
    return jsonify(films)


@watchlist_bp.route("/<user_id>/add", methods=["POST"])
def add_film(user_id):
    """
    POST /watchlist/<user_id>/add

    Body: { "film_id": "<uuid>", "public": false }

    "public" is optional and defaults to False (private); pass true to
    make the entry publicly visible.
    """
    data = request.get_json()
    if not data or "film_id" not in data:
        return jsonify({"error": "film_id is required"}), 400

    entry = add_to_watchlist(
        user_id=user_id,
        film_id=data["film_id"],
        public=data.get("public", False),
    )
    return jsonify(entry.to_dict()), 201
