"""
summary.py — ESPN Summary / Box Score API client.

Endpoint:
    https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={GAME_ID}

Purpose:
    Pull a full box score (or live stats) for a specific game identified by
    GAME_ID, which is obtained from the Scoreboard API.  Returns team-level
    stats, individual player stat lines, venue / officials info, and the list
    of PLAYER_IDs needed by the Gamelog and Athlete APIs.
"""

import requests

SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
)

_TIMEOUT = 10


def get_summary(game_id: str) -> dict:
    """
    Fetch the full game summary / box score for a single NBA game.

    Args:
        game_id: ESPN game identifier (from the Scoreboard API).

    Returns:
        A dict with the following keys:
            game_id       (str)   — the requested game ID
            status        (str)   — "Scheduled" / "In Progress" / "Final"
            home_team     (str)   — home team display name
            away_team     (str)   — away team display name
            home_score    (str)   — home score
            away_score    (str)   — away score
            venue         (str)   — arena name
            officials     (list)  — referee display names
            team_stats    (list)  — list of {team, stat_name, value} dicts
            player_stats  (list)  — list of player stat-line dicts
            player_ids    (list)  — PLAYER_IDs for all rostered athletes

    Raises:
        RuntimeError: If the HTTP request fails or the response is malformed.
    """
    try:
        response = requests.get(
            SUMMARY_URL, params={"event": game_id}, timeout=_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Summary API request failed for game {game_id}: {exc}"
        ) from exc
    except ValueError as exc:
        raise RuntimeError(
            f"Summary API returned invalid JSON for game {game_id}: {exc}"
        ) from exc

    # --- Header info -----------------------------------------------------------
    header = data.get("header", {})
    competitions = header.get("competitions", [{}])
    comp = competitions[0] if competitions else {}
    competitors = comp.get("competitors", [])

    home_team = away_team = "Unknown"
    home_score = away_score = "0"
    for c in competitors:
        name = c.get("team", {}).get("displayName", "Unknown")
        score = c.get("score", "0")
        if c.get("homeAway") == "home":
            home_team, home_score = name, score
        else:
            away_team, away_score = name, score

    status = comp.get("status", {}).get("type", {}).get("description", "Unknown")

    # --- Venue / officials -----------------------------------------------------
    game_info = data.get("gameInfo", {})
    venue = game_info.get("venue", {}).get("fullName", "Unknown Arena")
    officials = [
        o.get("displayName", "")
        for o in game_info.get("officials", [])
        if o.get("displayName")
    ]

    # --- Team stats ------------------------------------------------------------
    team_stats = []
    for team_box in data.get("boxscore", {}).get("teams", []):
        team_name = team_box.get("team", {}).get("displayName", "Unknown")
        for stat in team_box.get("statistics", []):
            team_stats.append(
                {
                    "team": team_name,
                    "stat_name": stat.get("label", stat.get("name", "")),
                    "value": stat.get("displayValue", stat.get("value", "")),
                }
            )

    # --- Player stats + IDs ----------------------------------------------------
    player_stats = []
    player_ids = []
    for team_players in data.get("boxscore", {}).get("players", []):
        team_name = team_players.get("team", {}).get("displayName", "Unknown")
        for stat_group in team_players.get("statistics", []):
            keys = stat_group.get("keys", [])
            labels = stat_group.get("labels", keys)
            for athlete_entry in stat_group.get("athletes", []):
                athlete = athlete_entry.get("athlete", {})
                pid = athlete.get("id", "")
                if pid and pid not in player_ids:
                    player_ids.append(pid)

                stats_values = athlete_entry.get("stats", [])
                stat_line = {
                    "player_id": pid,
                    "player_name": athlete.get("displayName", "Unknown"),
                    "team": team_name,
                    "position": athlete.get("position", {}).get(
                        "abbreviation", "N/A"
                    ),
                    "starter": athlete_entry.get("starter", False),
                    "active": athlete_entry.get("active", True),
                    "did_not_play": athlete_entry.get("didNotPlay", False),
                    "reason": athlete_entry.get("reason", ""),
                    "stats": dict(zip(labels, stats_values)),
                }
                player_stats.append(stat_line)

    return {
        "game_id": game_id,
        "status": status,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "venue": venue,
        "officials": officials,
        "team_stats": team_stats,
        "player_stats": player_stats,
        "player_ids": player_ids,
    }


def print_summary(summary: dict) -> None:
    """Pretty-print the game summary returned by :func:`get_summary`."""
    print(
        f"  {summary['away_team']} {summary['away_score']} @ "
        f"{summary['home_team']} {summary['home_score']}  |  "
        f"{summary['status']}  |  {summary['venue']}"
    )

    if summary["officials"]:
        print(f"  Officials: {', '.join(summary['officials'])}")

    # Print a compact team-stats table
    if summary["team_stats"]:
        print("\n  -- Team Stats --")
        # Group by stat_name for side-by-side display
        stat_map: dict[str, dict] = {}
        for row in summary["team_stats"]:
            stat_map.setdefault(row["stat_name"], {})[row["team"]] = row["value"]

        teams = list({r["team"] for r in summary["team_stats"]})
        header = f"  {'Stat':<30}" + "".join(f"{t:<20}" for t in teams)
        print(header)
        print("  " + "-" * (30 + 20 * len(teams)))
        for stat_name, team_vals in stat_map.items():
            row_str = f"  {stat_name:<30}" + "".join(
                f"{team_vals.get(t, '-'):<20}" for t in teams
            )
            print(row_str)

    # Print active player stat lines
    if summary["player_stats"]:
        print("\n  -- Player Stats --")
        active = [p for p in summary["player_stats"] if not p["did_not_play"]]
        for p in active[:10]:  # limit output to first 10 for readability
            stats_str = "  ".join(
                f"{k}:{v}" for k, v in list(p["stats"].items())[:6]
            )
            starter_flag = "* " if p["starter"] else "  "
            print(
                f"  {starter_flag}{p['player_name']:<25} {p['team']:<20} "
                f"{p['position']:<4}  {stats_str}"
            )
        if len(active) > 10:
            print(f"  ... and {len(active) - 10} more players")
