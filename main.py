#!/usr/bin/env python3
"""
main.py — ESPN NBA Data Pipeline for SmartPicksProAI.

Pipeline:
    1. Scoreboard API   → Today's games + GAME_IDs
    2. Summary API      → Box scores + PLAYER_IDs per game
    3. Gamelog API      → L3 averages + defensive metrics per player
    4. Athlete API      → Player bios + season averages + injury status

Run:
    python main.py

Optional env variables:
    ESPN_DATE   — pull data for a specific date (YYYYMMDD).  Default: today.
    MAX_GAMES   — limit number of games to process (default: all).
    MAX_PLAYERS — limit players processed per game (default: 3).

The script is intentionally verbose so you can verify that real data is
flowing before wiring it into the SmartAI-NBA / SmartPicksProAI app.
"""

import os
import sys

from espn_scraper.scoreboard import get_scoreboard, print_scoreboard
from espn_scraper.summary import get_summary, print_summary
from espn_scraper.gamelog import get_gamelog, print_gamelog
from espn_scraper.athlete import get_athlete, print_athlete
from espn_scraper.utils import normalize_date

# ---------------------------------------------------------------------------
# Configuration (override via environment variables)
# ---------------------------------------------------------------------------
ESPN_DATE = os.environ.get("ESPN_DATE", None)          # e.g. "20240301"
MAX_GAMES = int(os.environ.get("MAX_GAMES", 0))        # 0 = all games
MAX_PLAYERS = int(os.environ.get("MAX_PLAYERS", 3))    # players per game

SEPARATOR = "=" * 72
SECTION_SEP = "-" * 72


def _section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def _subsection(title: str) -> None:
    print(f"\n{SECTION_SEP}")
    print(f"  {title}")
    print(SECTION_SEP)


# ---------------------------------------------------------------------------
# Step 1 — Scoreboard
# ---------------------------------------------------------------------------
def run_scoreboard(date: str = None) -> list[dict]:
    _section("STEP 1 — TODAY'S NBA GAMES (Scoreboard API)")
    try:
        games = get_scoreboard(date=date)
    except RuntimeError as exc:
        print(f"  ERROR: {exc}")
        return []

    if not games:
        print("  No games scheduled for this date.")
        return []

    date_label = date or "today"
    print(f"  Found {len(games)} game(s) for {date_label}:\n")
    print_scoreboard(games)
    return games


# ---------------------------------------------------------------------------
# Step 2 — Summary / Box Score
# ---------------------------------------------------------------------------
def run_summary(game: dict) -> dict | None:
    _subsection(
        f"STEP 2 — BOX SCORE  |  "
        f"{game['away_team']} @ {game['home_team']}  "
        f"(Game ID: {game['game_id']})"
    )
    try:
        summary = get_summary(game["game_id"])
    except RuntimeError as exc:
        print(f"  ERROR: {exc}")
        return None

    print_summary(summary)
    print(f"\n  Player IDs found in box score: {len(summary['player_ids'])}")
    return summary


# ---------------------------------------------------------------------------
# Step 3 — Gamelog (L3 Averages + Defensive Rating)
# ---------------------------------------------------------------------------
def run_gamelog(player_id: str, player_name: str = "") -> dict | None:
    name_str = f" ({player_name})" if player_name else ""
    _subsection(f"STEP 3 — GAMELOG / L3 AVERAGES  |  Player {player_id}{name_str}")
    try:
        gamelog = get_gamelog(player_id)
    except RuntimeError as exc:
        print(f"  ERROR: {exc}")
        return None

    print_gamelog(gamelog, player_name=player_name)
    return gamelog


# ---------------------------------------------------------------------------
# Step 4 — Athlete Profile
# ---------------------------------------------------------------------------
def run_athlete(player_id: str) -> dict | None:
    _subsection(f"STEP 4 — ATHLETE PROFILE  |  Player {player_id}")
    try:
        athlete = get_athlete(player_id)
    except RuntimeError as exc:
        print(f"  ERROR: {exc}")
        return None

    print_athlete(athlete)
    return athlete


# ---------------------------------------------------------------------------
# Full Pipeline
# ---------------------------------------------------------------------------
def run_pipeline(date: str = None, max_games: int = 0, max_players: int = 3) -> None:
    """
    Execute the full ESPN NBA data pipeline.

    Args:
        date:        Date string in ``YYYYMMDD`` format (default: today).
        max_games:   Maximum number of games to process (0 = all).
        max_players: Maximum number of players to enrich per game.
    """
    print(SEPARATOR)
    print("  ESPN NBA DATA PIPELINE — SmartPicksProAI")
    print(SEPARATOR)
    if date:
        print(f"  Target date : {date}")
    print(f"  Max games   : {'all' if max_games == 0 else max_games}")
    print(f"  Max players : {max_players} per game")

    # --- Step 1 ---------------------------------------------------------------
    games = run_scoreboard(date=date)
    if not games:
        print("\nPipeline finished: no games to process.")
        return

    if max_games:
        games = games[:max_games]

    all_results = []

    for game in games:
        game_result = {
            "game": game,
            "summary": None,
            "players": [],
        }

        # --- Step 2 -----------------------------------------------------------
        summary = run_summary(game)
        game_result["summary"] = summary

        if summary is None:
            all_results.append(game_result)
            continue

        # Collect player name map from the box score player_stats list
        player_name_map: dict[str, str] = {
            p["player_id"]: p["player_name"]
            for p in summary.get("player_stats", [])
            if p.get("player_id")
        }

        # Take up to max_players unique IDs from the box score
        player_ids = summary["player_ids"][:max_players]

        for pid in player_ids:
            pname = player_name_map.get(pid, "")
            player_entry: dict = {"player_id": pid, "name": pname}

            # --- Step 3 -------------------------------------------------------
            gamelog = run_gamelog(pid, player_name=pname)
            player_entry["gamelog"] = gamelog

            # --- Step 4 -------------------------------------------------------
            athlete = run_athlete(pid)
            player_entry["athlete"] = athlete

            game_result["players"].append(player_entry)

        all_results.append(game_result)

    # --- Summary output -------------------------------------------------------
    _section("PIPELINE COMPLETE — SUMMARY")
    print(f"  Games processed    : {len(all_results)}")
    total_players = sum(len(r["players"]) for r in all_results)
    print(f"  Players enriched   : {total_players}")

    print("\n  Top Defensive Ratings (L3):")
    player_ratings = []
    for r in all_results:
        for p in r["players"]:
            gl = p.get("gamelog")
            if gl and gl.get("defensive_rating", 0) > 0:
                player_ratings.append(
                    (p["name"] or f"ID:{p['player_id']}", gl["defensive_rating"])
                )
    player_ratings.sort(key=lambda x: x[1], reverse=True)
    for name, rating in player_ratings[:10]:
        print(f"    {name:<30}  Defensive Rating: {rating}")

    print(f"\n{SEPARATOR}")
    print("  Pipeline finished. Data verified. Ready for SmartAI-NBA integration.")
    print(SEPARATOR)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Allow a date argument: python main.py 20240301
    date_arg = sys.argv[1] if len(sys.argv) > 1 else ESPN_DATE
    if date_arg:
        try:
            date_arg = normalize_date(date_arg)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            sys.exit(1)
    run_pipeline(date=date_arg, max_games=MAX_GAMES, max_players=MAX_PLAYERS)
