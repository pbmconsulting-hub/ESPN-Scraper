"""
athlete.py — ESPN Athlete API client.

Endpoint:
    https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{PLAYER_ID}

Purpose:
    Pull a player's bio, physical stats, current team, draft info, season
    averages (PPG / RPG / APG etc.), injury status, and recent news.

Usage:
    player_id is obtained from the Summary (box score) API via the PLAYER_IDs
    list, or from the Gamelog API.
"""

import requests

ATHLETE_URL = (
    "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
    "/athletes/{player_id}"
)

_TIMEOUT = 10


def get_athlete(player_id: str) -> dict:
    """
    Fetch profile and season averages for a single NBA player.

    Args:
        player_id: ESPN athlete identifier.

    Returns:
        A dict with the following keys:
            player_id       (str)   — ESPN athlete ID
            full_name       (str)   — display name
            first_name      (str)
            last_name       (str)
            dob             (str)   — date of birth (ISO format or empty)
            age             (int)
            jersey          (str)   — jersey number
            position        (str)   — position abbreviation
            height          (str)   — e.g. "6'9\""
            weight          (str)   — e.g. "250 lbs"
            college         (str)
            draft_year      (int)
            draft_round     (int)
            draft_pick      (int)
            team            (str)   — current team display name
            team_abbrev     (str)
            headshot_url    (str)
            injury_status   (str)   — "Active", "Questionable", "Out", etc.
            injury_desc     (str)   — injury description if applicable
            season_averages (dict)  — {stat_label: value} from ESPN
            news            (list)  — recent headline strings

    Raises:
        RuntimeError: If the HTTP request fails or the response is malformed.
    """
    url = ATHLETE_URL.format(player_id=player_id)
    try:
        response = requests.get(url, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Athlete API request failed for player {player_id}: {exc}"
        ) from exc
    except ValueError as exc:
        raise RuntimeError(
            f"Athlete API returned invalid JSON for player {player_id}: {exc}"
        ) from exc

    athlete = data.get("athlete", {})

    # --- Bio -------------------------------------------------------------------
    full_name = athlete.get("displayName", "Unknown")
    first_name = athlete.get("firstName", "")
    last_name = athlete.get("lastName", "")
    dob = athlete.get("dateOfBirth", "")
    age = athlete.get("age", 0)
    jersey = athlete.get("jersey", "")
    position = athlete.get("position", {}).get("abbreviation", "N/A")

    # --- Physical --------------------------------------------------------------
    height = athlete.get("displayHeight", "")
    weight = athlete.get("displayWeight", "")

    # --- Background ------------------------------------------------------------
    college_info = athlete.get("college", {})
    college = college_info.get("name", "") if isinstance(college_info, dict) else ""
    draft = athlete.get("draft", {})
    draft_year = draft.get("year", 0)
    draft_round = draft.get("round", 0)
    draft_pick = draft.get("selection", 0)

    # --- Team ------------------------------------------------------------------
    team_info = athlete.get("team", {})
    team = team_info.get("displayName", "Unknown")
    team_abbrev = team_info.get("abbreviation", "")

    # --- Headshot --------------------------------------------------------------
    headshot = athlete.get("headshot", {})
    headshot_url = headshot.get("href", "") if isinstance(headshot, dict) else ""

    # --- Injury ----------------------------------------------------------------
    injuries = athlete.get("injuries", [])
    injury_status = "Active"
    injury_desc = ""
    if injuries:
        latest = injuries[0]
        injury_status = latest.get("status", "Unknown")
        injury_desc = latest.get("longComment", latest.get("shortComment", ""))

    # --- Season averages -------------------------------------------------------
    season_averages: dict = {}
    stats_block = data.get("stats", {})
    # ESPN may return stats as a list of category objects or a dict
    if isinstance(stats_block, list):
        for cat in stats_block:
            labels = cat.get("labels", [])
            values = cat.get("values", [])
            for lbl, val in zip(labels, values):
                season_averages[lbl] = val
    elif isinstance(stats_block, dict):
        for cat in stats_block.get("categories", []):
            labels = cat.get("labels", [])
            values = cat.get("values", [])
            for lbl, val in zip(labels, values):
                season_averages[lbl] = val

    # Some versions nest averages under 'athlete' → 'statistics'
    if not season_averages:
        for cat in athlete.get("statistics", {}).get("categories", []):
            labels = cat.get("labels", [])
            values = cat.get("values", [])
            for lbl, val in zip(labels, values):
                season_averages[lbl] = val

    # --- News ------------------------------------------------------------------
    news = []
    for article in data.get("news", {}).get("articles", []):
        headline = article.get("headline", "")
        if headline:
            news.append(headline)

    return {
        "player_id": player_id,
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "age": age,
        "jersey": jersey,
        "position": position,
        "height": height,
        "weight": weight,
        "college": college,
        "draft_year": draft_year,
        "draft_round": draft_round,
        "draft_pick": draft_pick,
        "team": team,
        "team_abbrev": team_abbrev,
        "headshot_url": headshot_url,
        "injury_status": injury_status,
        "injury_desc": injury_desc,
        "season_averages": season_averages,
        "news": news,
    }


def print_athlete(athlete: dict) -> None:
    """Pretty-print the athlete profile returned by :func:`get_athlete`."""
    print(
        f"  {athlete['full_name']}  |  #{athlete['jersey']}  {athlete['position']}  "
        f"|  {athlete['team']} ({athlete['team_abbrev']})  "
        f"|  Age: {athlete['age']}  |  {athlete['height']} / {athlete['weight']}"
    )
    if athlete["college"]:
        draft_info = (
            f"Draft: {athlete['draft_year']} Rd {athlete['draft_round']} Pick {athlete['draft_pick']}"
            if athlete["draft_year"]
            else "Undrafted"
        )
        print(f"  College: {athlete['college']}  |  {draft_info}")

    print(
        f"  Injury Status: {athlete['injury_status']}"
        + (f"  — {athlete['injury_desc']}" if athlete["injury_desc"] else "")
    )

    if athlete["season_averages"]:
        avgs = athlete["season_averages"]
        key_stats = ["PTS", "REB", "AST", "STL", "BLK", "TO", "FG%", "3P%", "GP"]
        parts = []
        for k in key_stats:
            if k in avgs:
                parts.append(f"{k}:{avgs[k]}")
        if not parts:
            # Fall back to first 8 items if key stats not found
            parts = [f"{k}:{v}" for k, v in list(avgs.items())[:8]]
        print(f"  Season Averages: {' | '.join(parts)}")

    if athlete["news"]:
        print(f"  Latest News: {athlete['news'][0]}")
