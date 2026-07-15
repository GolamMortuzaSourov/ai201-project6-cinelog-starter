# PR Response Doc — CineLog Watchlist Feature

## AI Usage
I used AI (Claude Code) throughout this project:

- **Orientation.** Summarized `models.py`, `services/collection_service.py`, and `tests/test_collection.py` to understand the existing naming convention, deduplication pattern, and test fixtures before reading the review comments.
- **Code comments (1, 2, 3, 6).** Implemented the rename, the deduplication check plus `UniqueConstraint`, and the watchlist tests, and performed the rebase onto `main` including the integer→UUID conflict resolution. During end-to-end verification it also flagged a pre-existing `get_watchlist` bug (the missing `WatchlistEntry.film` relationship), which was then fixed.
- **Visibility toggle and sort option.** Implemented the opt-in `public` parameter and the `?sort=` option.
- **History hygiene.** Rewrote the commit history into conventional, one-change-per-commit form and checked the log format.
- **Design decisions (4 & 5) — positions mine, AI as sounding board.** The decisions are mine: private-by-default with opt-in sharing (Comment 4), and offering both sort orders with date-added as the default (Comment 5). I gave my reasoning and used AI to draft it into the write-ups above and to stress-test it. One concrete catch: when I chose "keep both sort options," my stated reason ("alphabetical is easier to find") actually argued against the date-added default I'd picked — the stress-test surfaced that contradiction, and I resolved it by making sort configurable with date-added as the documented default.

## Comment 1 — Rename
> *Reviewer:* "`save_to_watchlist()` should follow the project's naming convention. Compare with `add_to_collection()` — the pattern here is verb_to_noun. Please rename to `add_to_watchlist()` and update all call sites."

**What I did:**
Renamed `save_to_watchlist()` to `add_to_watchlist()` in `services/watchlist_service.py` and updated the one call site — the import and the call in the `POST /watchlist/<user_id>/add` handler in `routes/watchlist/watchlist.py`. This matches the existing `add_to_collection()` / `remove_from_collection()` / `get_collection()` naming in `services/collection_service.py`. Committed as a `refactor:` since there is no behavior change.

**How I verified:**
`grep -rn "save_to_watchlist"` across the `.py` files returns no matches. `pytest tests/` stays green (the rename doesn't touch collection behavior, and the watchlist tests added in Comment 3 exercise the new name).

## Comment 2 — Deduplication
> *Reviewer:* "What happens if a user calls this with a film that's already on their watchlist? The current implementation would add a duplicate entry. Please handle this case."

**What I did:**
Two layers, mirroring how the collection feature already handles this:
1. **Service check** — `add_to_watchlist()` now queries for an existing `(user_id, film_id)` entry after confirming the film exists, and raises a new `AlreadyInWatchlistError` if one is found (parallel to `AlreadyInCollectionError` in `add_to_collection()`).
2. **Database backstop** — added a `UniqueConstraint("user_id", "film_id", name="unique_user_film_watchlist")` to `WatchlistEntry`, matching `CollectionEntry`'s `unique_user_film_collection`. This guarantees no duplicate can be persisted even if a caller bypasses the service.

**How I verified:**
`test_add_to_watchlist_duplicate_raises` adds the same film twice, asserts `AlreadyInWatchlistError` is raised, and confirms exactly one row exists. Full suite: 10 passed.

## Comment 3 — Missing test
> *Reviewer:* "Please add a test for the case where `film_id` doesn't exist in the database. Look at the existing tests in `test_collection.py` — the pattern is there."

**What I did:**
Created `tests/test_watchlist.py` following the `test_collection.py` structure (in-memory `app`, `sample_user`, `sample_film` fixtures). It includes the specifically requested case — `test_add_to_watchlist_nonexistent_film_raises`, which asserts `FilmNotFoundError` for an id with no matching film — plus the happy-path and duplicate cases so the new service function has the full trio CONTRIBUTING.md requires.

**How I verified:**
`pytest tests/` → 10 passed (4 collection + 6 watchlist). The nonexistent-film test uses the same fake id string the collection test uses, so it holds before and after the UUID rebase.

## Comment 4 — Default visibility
> *Reviewer:* "watchlists default to `public=True`. We don't have a documented decision on default visibility... add a note to your PR description explaining your reasoning."

**My position:** Default watchlist entries to **private** (`public=False`), and add an optional `public` flag so a user can opt in to sharing.

**Reasoning:**
A watchlist is a list of films a user *hasn't watched yet* — it signals intent, not activity, and that's more personal than a public "films I've seen" collection. Defaulting to private means a user never accidentally broadcasts what they're planning to watch. But CineLog is still a community app, so sharing should be possible — just chosen, not assumed. Making `public` an explicit opt-in gives the user control instead of inheriting a default they never agreed to (which is the "be intentional" point the reviewer raised).

**Tradeoff acknowledged:**
A private default means fewer watchlists are discoverable out of the box, so the community/discovery side of the product is weaker until users actively opt in. I'm accepting that cost because defaulting to *consent* matters more than defaulting to *reach* — and users who want the social experience can still turn it on.

## Comment 5 — Sort order
> *Reviewer:* "I'd prefer watchlists to default to 'date added' order rather than alphabetical. Most users want to see what they added recently. I'm open to discussion if you see it differently — but let's make a decision and document it."

**My position:** Make sort order a **choice**. `get_watchlist()` / `GET /watchlist/<user_id>` accept `?sort=`, supporting `date_added` (**default**, newest first, matching `get_collection`) and `title` (alphabetical).

**Reasoning:**
Different users open a watchlist for different reasons: some want to see what they just added (recency), others want to scan the whole list by title to pick something to watch tonight. Rather than force one ordering on everyone, I expose both and pick a sensible default. I kept `date_added` as the default because "what did I add recently" is the more common first question when you open a watchlist — but alphabetical is always one query param away.

**Engagement with reviewer's point:**
I agree with the maintainer that "most users want to see what they added recently" — that's why date-added is the default, not just an option. Where I'd push back is on it being the *only* order: for a watchlist that grows to dozens of films, browsing alphabetically is how you actually find a specific title, so `?sort=title` keeps that path open without changing the default behavior they asked for.

## Comment 6 — Rebase
> *Reviewer:* "A refactor merged to main that changed film IDs from integers to UUIDs. Your watchlist code still references integer IDs. Please rebase on main and update accordingly."

**What conflicted:**
`git rebase origin/main` replayed the branch's five commits onto the post-refactor `main`. The single content conflict was in `models.py`: the incoming `WatchlistEntry` defined `film_id = db.Column(db.Integer, db.ForeignKey("film.id"))`, while `main` had migrated `Film.id` (and `CollectionEntry.film_id`) to `db.String(36)` UUIDs.

**How I resolved it:**
Changed `WatchlistEntry.film_id` to `db.Column(db.String(36), db.ForeignKey("film.id"), nullable=False)` so the foreign key matches the UUID `Film.id`. I also updated the two remaining integer references in the docstring of `add_to_watchlist()` (`film_id (str): UUID of the film`) and the request-body comment in the route (`"film_id": "<uuid>"`). The nonexistent-film test already used a UUID-shaped id, so it needed no change.

**How I verified no conflict remains:**
- `git log --merges origin/main..HEAD` → empty (no merge commits; linear history).
- `pytest tests/` → 10 passed.
- End-to-end smoke test through the Flask test client: `POST /watchlist/<uuid>/add` returns 201 with a UUID `film_id`, and the duplicate-add correctly raises `AlreadyInWatchlistError`.

**Backup:** `backup/watchlist-pre-rebase` branch points at the pre-rebase state (`git reflog` also available) in case a redo is needed.

## Additional fix — get_watchlist relationship (found during verification)
Not one of the six review comments, but surfaced when smoke-testing the endpoints end to end: `GET /watchlist/<user_id>` raised `AttributeError: 'WatchlistEntry' object has no attribute 'film'` whenever the list was non-empty. `get_watchlist()` builds each result with `entry.film.to_dict()`, but `WatchlistEntry` had no `film` relationship — `Film` only declared `collection_entries` (whose `backref="film"` serves `CollectionEntry`, not `WatchlistEntry`).

**Fix:** added `watchlist_entries = db.relationship("WatchlistEntry", backref="film", lazy=True)` on `Film`, mirroring `collection_entries`. **Verified:** new test `test_get_watchlist_returns_saved_films` passes; smoke test of `GET /watchlist/<user_id>` now returns 200 with the saved film. It went unnoticed originally because no test exercised `get_watchlist()`.

## PR Description

**What the feature does**
Adds a watchlist so users can save films they intend to watch later (distinct from the collection, which tracks films already watched). Introduces a `WatchlistEntry` model, `add_to_watchlist()` / `get_watchlist()` service functions, and two endpoints:
- `POST /watchlist/<user_id>/add` — add a film. Body: `{"film_id": "<uuid>", "public": <bool, optional>}`.
- `GET /watchlist/<user_id>` — list the user's watchlist. Optional `?sort=date_added|title`.

A film cannot be added to the same watchlist twice.

**Design decisions**
- **Default visibility (Comment 4):** entries are **private by default** (`public=False`); callers opt in to sharing by passing `public: true`. Full reasoning under Comment 4.
- **Sort order (Comment 5):** results are **newest-first by default** (`date_added`), with `?sort=title` for alphabetical. Full reasoning under Comment 5.

**How to test manually**
```bash
pip install -r requirements.txt
python app.py   # serves on http://127.0.0.1:5000 (no frontend — use curl)
```
In a second shell, seed a user and a film and note their UUIDs:
```bash
python -c "
from app import create_app, db
from models import User, Film
app = create_app()
with app.app_context():
    u = User(username='alice', email='alice@example.com')
    f = Film(title='Dune', year=2021, genre='Sci-Fi')
    db.session.add_all([u, f]); db.session.commit()
    print('USER', u.id); print('FILM', f.id)
"
```
Then exercise the endpoints (substitute the printed UUIDs):
```bash
# Add privately (default)
curl -X POST http://127.0.0.1:5000/watchlist/<USER_ID>/add \
  -H 'Content-Type: application/json' -d '{"film_id": "<FILM_ID>"}'
# -> 201 with "public": false

# View watchlist (newest first)
curl http://127.0.0.1:5000/watchlist/<USER_ID>

# View alphabetically
curl "http://127.0.0.1:5000/watchlist/<USER_ID>?sort=title"
```
Adding a film already on the watchlist is rejected (`AlreadyInWatchlistError`), and a nonexistent `film_id` raises `FilmNotFoundError`.

## Commit history
`git log --oneline origin/main..HEAD` on `feature/watchlist`, newest first:

- `docs: add PR response doc`
- `test: add watchlist service tests`
- `feat: support sortable watchlist ordering`
- `feat: default watchlist entries to private with opt-in public flag`
- `fix: add WatchlistEntry-Film relationship for get_watchlist`
- `fix: prevent duplicate entries when adding to watchlist`
- `refactor: rename save_to_watchlist to add_to_watchlist`
- `feat: add watchlist model, service, and endpoints`

8 commits, conventional format, one logical change each, no merge commits, rebased on `main`. *(Replace with a screenshot of `git log --oneline` for submission.)*
