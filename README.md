# ESPN-Scraper

**ESPN NBA Data Scraper for SmartPicksProAI / SmartAI-NBA**

A modular Python application that pulls live NBA data from ESPN's unofficial
(hidden) APIs and chains them together into a single data pipeline.  The
pipeline is the data-gathering backbone for SmartPicksProAI prop-betting
projections.

---

## Features

- **4-API pipeline** — Scoreboard → Summary → Gamelog → Athlete
- **L3 (Last 3 Games) averaging** for PTS, REB, AST, STL, BLK, TO, MIN
- **Dynamic label indexing** so the pipeline won't break if ESPN reorders columns
- **Custom Defensive Rating** formula weighted for prop-betting models
- Robust error handling (API failures, off-season, missing data)
- Zero authentication required — ESPN's APIs are publicly accessible

---

## ESPN API Endpoints Used

| # | API | URL | Purpose |
|---|-----|-----|---------|
| 1 | **Scoreboard** | `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard` | Today's games + GAME_IDs |
| 2 | **Summary / Box Score** | `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={GAME_ID}` | Per-game box scores + PLAYER_IDs |
| 3 | **Gamelog** | `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{PLAYER_ID}/gamelog` | Season game log → L3 averages |
| 4 | **Athlete** | `https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{PLAYER_ID}` | Player bios, season averages, injury status |

---

## Data Pipeline Flow

```
1. Scoreboard API         →  Who's playing today? Get GAME_IDs
        │
        ▼
2. Summary/Box Score API  →  Get rosters & PLAYER_IDs for today's games
        │
        ▼
3. Gamelog API             →  Pull each player's season game log → slice [:3]
        │                      for L3 averages (PTS, REB, AST, etc.)
        ▼
4. Athlete API             →  Enrich with bios, injury status, season averages
        │
        ▼
   Output                  →  Printed results for verification
```

---

## Project Structure

```
ESPN-Scraper/
├── main.py                  # Full pipeline entry point
├── requirements.txt         # Python dependencies
├── README.md
└── espn_scraper/            # Modular API clients
    ├── __init__.py
    ├── scoreboard.py        # Scoreboard API (today's games)
    ├── summary.py           # Summary/Box Score API (per-game stats)
    ├── gamelog.py           # Gamelog API (L3 averages, defensive metrics)
    └── athlete.py           # Athlete API (bios, season averages)
```

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/pbmconsulting-hub/ESPN-Scraper.git
cd ESPN-Scraper

# 2. (Optional) create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Usage

### Run the full pipeline (today's games)

```bash
python main.py
```

### Run for a specific date

```bash
python main.py 20240301     # March 1, 2024
```

### Environment variable overrides

| Variable | Default | Description |
|----------|---------|-------------|
| `ESPN_DATE` | today | Target date in `YYYYMMDD` format |
| `MAX_GAMES` | 0 (all) | Limit games processed |
| `MAX_PLAYERS` | 3 | Players enriched per game |

```bash
MAX_GAMES=2 MAX_PLAYERS=5 python main.py
```

---

## Defensive Rating Formula

The custom Defensive Rating used for SmartPicksProAI is calculated from L3
(last 3 games) per-game averages:

```
defensive_rating = (BLK × 3) + (STL × 3) + (REB × 1.2)
```

Blocks and steals are heavily weighted as high-value individual defensive plays.
Rebounds contribute at a lower weight due to their higher volume.

---

## Dynamic Label Indexing

The Gamelog API returns a `labels` array as a column decoder.  All stat
lookups use `labels.index('BLK')` instead of hard-coded positions — this
ensures the pipeline keeps working if ESPN reorders their columns, which is
critical for autonomous Azure Functions deployments.

```python
labels = response['seasonTypes'][0]['categories'][0]['labels']
blk_idx = labels.index('BLK')
stl_idx = labels.index('STL')
reb_idx = labels.index('REB')
```

---

## Using the Modules Directly

Each API client can be imported and used independently:

```python
from espn_scraper.scoreboard import get_scoreboard
from espn_scraper.summary import get_summary
from espn_scraper.gamelog import get_gamelog
from espn_scraper.athlete import get_athlete

# Get today's games
games = get_scoreboard()

# Get box score for a specific game (use a game_id from get_scoreboard())
summary = get_summary("401585185")

# Get L3 averages for a player (LeBron James = 1966)
gamelog = get_gamelog("1966")
print(gamelog["l3_averages"])
print(gamelog["defensive_rating"])

# Get player profile
athlete = get_athlete("1966")
print(athlete["season_averages"])
```

---

## Notes

- ESPN's APIs are **unofficial and undocumented**.  They can change or be
  rate-limited at any time without notice.
- No API key or authentication is required.
- Advanced metrics (Defensive Rating / DBPM) are not available from ESPN's
  basic gamelog; this app uses the custom formula above as a proxy.
- Intended for integration with **SmartAI-NBA / SmartPicksProAI**.
