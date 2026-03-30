"""
scoreboard.py — ESPN Scoreboard API client.

Endpoint:
    https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard

Purpose:
    Pull today's NBA games (or a specific date) and return a normalised list
    of game dicts containing the game ID, team names, scores, game status,
    venue, and broadcast info.  The GAME_IDs returned here are passed to the
    Summary API to drill into individual box scores.
"""

import requests

from espn_scraper.utils import normalize_date

SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
)

# Default request timeout in seconds
_TIMEOUT = 10


def get_scoreboard(date: str = None) -> list[dict]:
    """
    Fetch today's (or a given date's) NBA games from the ESPN Scoreboard API.

    Args:
        date: Optional date string in ``YYYYMMDD`` format.  If omitted the API
              returns today's schedule.

    Returns:
        A list of game dicts.  Each dict has the following keys:
            game_id      (str)  — ESPN unique game identifier
            status       (str)  — e.g. "Scheduled", "In Progress", "Final"
            clock        (str)  — game clock / period text (live games)
            home_team    (str)  — home team display name
            home_score   (str)  — home team score ("0" if not started)
            away_team    (str)  — away team display name
            away_score   (str)  — away team score ("0" if not started)
            venue        (str)  — arena name
            city         (str)  — arena city / state
            broadcasts   (list) — TV / streaming channel names

    Raises:
        RuntimeError: If the HTTP request fails or the response cannot be
                      parsed as expected.
    """
    params = {}
    if date:
        try:
            params["dates"] = normalize_date(date)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

    try:
        response = requests.get(SCOREBOARD_URL, params=params, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Scoreboard API request failed: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"Scoreboard API returned invalid JSON: {exc}") from exc

    events = data.get("events", [])
    if not events:
        return []

    games = []
    for event in events:
        game_id = event.get("id", "")
        status_type = event.get("status", {}).get("type", {})
        status = status_type.get("description", "Unknown")
        clock = event.get("status", {}).get("displayClock", "")
        period = event.get("status", {}).get("period", 0)
        if period:
            clock = f"Q{period} {clock}".strip()

        # Venue
        venue_info = event.get("competitions", [{}])[0].get("venue", {})
        venue = venue_info.get("fullName", "Unknown Arena")
        address = venue_info.get("address", {})
        city = f"{address.get('city', '')}, {address.get('state', '')}".strip(", ")

        # Broadcasts
        broadcast_list = event.get("competitions", [{}])[0].get("broadcasts", [])
        broadcasts = []
        for b in broadcast_list:
            broadcasts.extend([m.get("shortName", "") for m in b.get("media", [])])

        # Teams / scores
        competitors = event.get("competitions", [{}])[0].get("competitors", [])
        home_team = away_team = "TBD"
        home_score = away_score = "0"
        for comp in competitors:
            name = comp.get("team", {}).get("displayName", "Unknown")
            score = comp.get("score", "0")
            if comp.get("homeAway") == "home":
                home_team, home_score = name, score
            else:
                away_team, away_score = name, score

        games.append(
            {
                "game_id": game_id,
                "status": status,
                "clock": clock,
                "home_team": home_team,
                "home_score": home_score,
                "away_team": away_team,
                "away_score": away_score,
                "venue": venue,
                "city": city,
                "broadcasts": broadcasts,
            }
        )

    return games


def print_scoreboard(games: list[dict]) -> None:
    """Pretty-print the list of games returned by :func:`get_scoreboard`."""
    if not games:
        print("  No games found for this date.")
        return

    for i, g in enumerate(games, 1):
        bcast = ", ".join(g["broadcasts"]) if g["broadcasts"] else "N/A"
        score_line = f"{g['away_score']} – {g['home_score']}"
        print(
            f"  [{i}] {g['away_team']} @ {g['home_team']}  |  "
            f"{score_line}  |  {g['status']}  {g['clock']}  |  "
            f"ID: {g['game_id']}  |  {g['venue']} ({g['city']})  |  TV: {bcast}"
        )
