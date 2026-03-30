"""
gamelog.py — ESPN Gamelog API client with L3 averaging & defensive metrics.

Endpoint:
    https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{PLAYER_ID}/gamelog

Purpose:
    Pull a player's entire season of game-by-game stats and compute:
      - L3 (last 3 games) averages for key offensive & defensive stats
      - A custom Defensive Rating for SmartPicksProAI models

Implementation Details:
    * Dynamic label indexing (``labels.index('BLK')``) is used throughout so
      the pipeline won't break if ESPN reorders columns — critical for
      autonomous Azure Functions deployments.
    * Games are returned newest-first, so ``events[:3]`` gives the last 3.
"""

import requests

GAMELOG_URL = (
    "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
    "/athletes/{player_id}/gamelog"
)

# Stats we want to extract and average
STAT_LABELS = ["MIN", "PTS", "REB", "AST", "STL", "BLK", "TO"]

_TIMEOUT = 10


def _safe_float(value: str) -> float:
    """Convert a stat string to float, returning 0.0 on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def get_gamelog(player_id: str) -> dict:
    """
    Fetch a player's season gamelog and compute L3 averages.

    Args:
        player_id: ESPN athlete identifier (from the Summary API).

    Returns:
        A dict with the following keys:
            player_id       (str)   — the requested player ID
            season_type     (str)   — e.g. "Regular Season"
            labels          (list)  — stat column labels from ESPN
            all_games       (list)  — all game dicts for the season
            last_3_games    (list)  — the 3 most recent game dicts
            l3_averages     (dict)  — {stat_label: average} for STAT_LABELS
            defensive_rating (float) — custom defensive score (see formula)

    Raises:
        RuntimeError: If the HTTP request fails or the response is malformed.
    """
    url = GAMELOG_URL.format(player_id=player_id)
    try:
        response = requests.get(url, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Gamelog API request failed for player {player_id}: {exc}"
        ) from exc
    except ValueError as exc:
        raise RuntimeError(
            f"Gamelog API returned invalid JSON for player {player_id}: {exc}"
        ) from exc

    season_types = data.get("seasonTypes", [])
    if not season_types:
        return _empty_result(player_id, "No season data available")

    # Prefer Regular Season (type 2); fall back to the first available type
    season_block = None
    season_type_name = "Unknown"
    for st in season_types:
        if st.get("type") == 2 or st.get("name", "").lower() == "regular season":
            season_block = st
            season_type_name = st.get("name", "Regular Season")
            break
    if season_block is None:
        season_block = season_types[0]
        season_type_name = season_block.get("name", "Unknown")

    categories = season_block.get("categories", [])
    if not categories:
        return _empty_result(player_id, f"No categories in {season_type_name}")

    category = categories[0]
    labels = category.get("labels", [])
    events = category.get("events", [])

    if not events:
        return _empty_result(player_id, f"No games found in {season_type_name}")

    # Games come newest-first → slice top 3 for L3
    last_3 = events[:3]

    l3_averages = _compute_averages(last_3, labels)
    def_rating = _defensive_rating(l3_averages)

    return {
        "player_id": player_id,
        "season_type": season_type_name,
        "labels": labels,
        "all_games": events,
        "last_3_games": last_3,
        "l3_averages": l3_averages,
        "defensive_rating": def_rating,
    }


def _compute_averages(games: list, labels: list) -> dict:
    """
    Compute per-game averages for STAT_LABELS across *games*.

    Uses dynamic index lookup so the pipeline is resilient to ESPN column
    reordering.
    """
    totals = {label: 0.0 for label in STAT_LABELS}
    count = len(games)
    if count == 0:
        return totals

    for game in games:
        stats = game.get("stats", [])
        for label in STAT_LABELS:
            if label in labels:
                idx = labels.index(label)
                if idx < len(stats):
                    totals[label] += _safe_float(stats[idx])

    return {label: round(totals[label] / count, 2) for label in STAT_LABELS}


def _defensive_rating(averages: dict) -> float:
    """
    Compute a custom Defensive Rating for SmartPicksProAI.

    Formula (per-game L3 averages):
        defensive_rating = (BLK * 3) + (STL * 3) + (REB * 1.2)

    Blocks and steals are heavily weighted as high-value defensive plays.
    Rebounds contribute at a lower weight as they are higher-volume stats.
    """
    blocks = averages.get("BLK", 0.0)
    steals = averages.get("STL", 0.0)
    rebounds = averages.get("REB", 0.0)
    return round((blocks * 3) + (steals * 3) + (rebounds * 1.2), 2)


def _empty_result(player_id: str, reason: str) -> dict:
    """Return a safe empty result dict when no data is available."""
    return {
        "player_id": player_id,
        "season_type": reason,
        "labels": [],
        "all_games": [],
        "last_3_games": [],
        "l3_averages": {label: 0.0 for label in STAT_LABELS},
        "defensive_rating": 0.0,
    }


def print_gamelog(gamelog: dict, player_name: str = "") -> None:
    """Pretty-print the gamelog summary returned by :func:`get_gamelog`."""
    name_str = f" — {player_name}" if player_name else ""
    print(f"  Player ID {gamelog['player_id']}{name_str}  |  {gamelog['season_type']}")
    print(f"  Total games this season: {len(gamelog['all_games'])}")

    if gamelog["last_3_games"]:
        print("\n  -- Last 3 Games --")
        labels = gamelog["labels"]
        for game in gamelog["last_3_games"]:
            stats = game.get("stats", [])
            date = game.get("gameDate", game.get("date", "N/A"))
            opponent = game.get("opponent", {})
            if isinstance(opponent, dict):
                opp_name = opponent.get("displayName", opponent.get("abbreviation", "?"))
            else:
                opp_name = str(opponent)
            parts = []
            for lbl in STAT_LABELS:
                if lbl in labels:
                    idx = labels.index(lbl)
                    val = stats[idx] if idx < len(stats) else "N/A"
                    parts.append(f"{lbl}:{val}")
            print(f"    {date}  vs {opp_name:<15}  {' | '.join(parts)}")

    avgs = gamelog["l3_averages"]
    print("\n  -- L3 Averages --")
    avgs_str = "  ".join(f"{k}:{v}" for k, v in avgs.items())
    print(f"    {avgs_str}")
    print(f"  Defensive Rating (L3): {gamelog['defensive_rating']}")
