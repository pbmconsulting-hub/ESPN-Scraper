#!/usr/bin/env python3
"""
cli.py — Interactive CLI for the ESPN NBA Scraper.

Provides a menu-driven interface so you can run each pipeline step
independently and verify that data is flowing correctly.

Run:
    python cli.py
"""

import sys

from espn_scraper.scoreboard import get_scoreboard, print_scoreboard
from espn_scraper.summary import get_summary, print_summary
from espn_scraper.gamelog import get_gamelog, print_gamelog
from espn_scraper.athlete import get_athlete, print_athlete

SEPARATOR = "=" * 72
SECTION_SEP = "-" * 72

MENU = """
========================================================================
  ESPN NBA Scraper — Interactive Menu
========================================================================
  [1] View today's scoreboard
  [2] View scoreboard for a specific date
  [3] Get box score for a game (by Game ID)
  [4] Look up a player's gamelog / L3 averages (by Player ID)
  [5] Look up a player's profile (by Player ID)
  [6] Run full pipeline (scoreboard → box score → gamelog → profile)
  [q] Quit
========================================================================"""


def _prompt(text: str, default: str = "") -> str:
    """Prompt the user for input, returning *default* when they press Enter."""
    suffix = f" [{default}]" if default else ""
    value = input(f"  {text}{suffix}: ").strip()
    return value or default


def _section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def view_scoreboard(date: str | None = None) -> list[dict]:
    """Fetch and display the NBA scoreboard."""
    label = date if date else "today"
    _section(f"NBA SCOREBOARD — {label}")
    try:
        games = get_scoreboard(date=date)
    except RuntimeError as exc:
        print(f"  ERROR: {exc}")
        return []

    if not games:
        print("  No games found for this date.")
        return []

    print(f"  Found {len(games)} game(s):\n")
    print_scoreboard(games)
    return games


def view_summary(game_id: str) -> dict | None:
    """Fetch and display a box score."""
    _section(f"BOX SCORE — Game {game_id}")
    try:
        summary = get_summary(game_id)
    except RuntimeError as exc:
        print(f"  ERROR: {exc}")
        return None

    print_summary(summary)
    ids = summary.get("player_ids", [])
    print(f"\n  Player IDs in this game ({len(ids)}): {', '.join(ids[:20])}")
    if len(ids) > 20:
        print(f"  ... and {len(ids) - 20} more")
    return summary


def view_gamelog(player_id: str) -> dict | None:
    """Fetch and display a player's gamelog / L3 averages."""
    _section(f"GAMELOG — Player {player_id}")
    try:
        gamelog = get_gamelog(player_id)
    except RuntimeError as exc:
        print(f"  ERROR: {exc}")
        return None

    print_gamelog(gamelog, player_name=player_id)
    return gamelog


def view_athlete(player_id: str) -> dict | None:
    """Fetch and display a player profile."""
    _section(f"ATHLETE PROFILE — Player {player_id}")
    try:
        athlete = get_athlete(player_id)
    except RuntimeError as exc:
        print(f"  ERROR: {exc}")
        return None

    print_athlete(athlete)
    return athlete


def run_full_pipeline() -> None:
    """Interactive full pipeline: scoreboard → pick a game → box score → players."""
    date = _prompt("Date (YYYYMMDD or blank for today)")
    date = date if date else None

    games = view_scoreboard(date)
    if not games:
        return

    # Let the user pick a game
    print()
    choice = _prompt("Pick a game number (or 'all' for all games)", "1")
    if choice.lower() == "all":
        selected = games
    else:
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(games):
                print("  Invalid game number.")
                return
            selected = [games[idx]]
        except ValueError:
            print("  Invalid input.")
            return

    max_str = _prompt("Max players per game", "3")
    try:
        max_players = int(max_str)
    except ValueError:
        max_players = 3

    for game in selected:
        summary = view_summary(game["game_id"])
        if summary is None:
            continue

        player_ids = summary.get("player_ids", [])[:max_players]
        player_name_map: dict[str, str] = {
            p["player_id"]: p["player_name"]
            for p in summary.get("player_stats", [])
            if p.get("player_id")
        }

        for pid in player_ids:
            pname = player_name_map.get(pid, pid)
            _section(f"GAMELOG — {pname} (ID: {pid})")
            try:
                gamelog = get_gamelog(pid)
                print_gamelog(gamelog, player_name=pname)
            except RuntimeError as exc:
                print(f"  ERROR: {exc}")

            _section(f"ATHLETE PROFILE — {pname} (ID: {pid})")
            try:
                athlete = get_athlete(pid)
                print_athlete(athlete)
            except RuntimeError as exc:
                print(f"  ERROR: {exc}")

    print(f"\n{SEPARATOR}")
    print("  Pipeline complete!")
    print(SEPARATOR)


def main() -> None:
    """Run the interactive menu loop."""
    while True:
        print(MENU)
        choice = input("  Enter choice: ").strip().lower()

        if choice == "1":
            view_scoreboard()

        elif choice == "2":
            date = _prompt("Enter date (YYYYMMDD)")
            if date:
                view_scoreboard(date)
            else:
                print("  No date entered.")

        elif choice == "3":
            game_id = _prompt("Enter Game ID")
            if game_id:
                view_summary(game_id)
            else:
                print("  No Game ID entered.")

        elif choice == "4":
            player_id = _prompt("Enter Player ID")
            if player_id:
                view_gamelog(player_id)
            else:
                print("  No Player ID entered.")

        elif choice == "5":
            player_id = _prompt("Enter Player ID")
            if player_id:
                view_athlete(player_id)
            else:
                print("  No Player ID entered.")

        elif choice == "6":
            run_full_pipeline()

        elif choice in ("q", "quit", "exit"):
            print("  Goodbye!")
            break

        else:
            print("  Unknown option. Please try again.")


if __name__ == "__main__":
    main()
