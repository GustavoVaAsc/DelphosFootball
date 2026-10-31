# Transfermarkt Dataset — Data Discovery Profile

Generated: 2026-10-11 23:19 from `data/Dataset/*.csv` (12 files, 873.4 MB, read-only).
All numbers below were computed by re-runnable profiling scripts in `discovery/` (pandas 3.0.6, python 3.12; big files streamed in 250k-row chunks / read with `usecols`).
Regenerate with `bash discovery/run_all.sh`; raw per-step outputs live in `discovery/results/*.json`.
Reference date for 'future-dated' checks: 2026-10-11.

## 1. File inventory

| file | rows | cols | size | granularity | primary key candidate (verified unique) | date coverage |
|---|---:|---:|---:|---|---|---|
| `appearances.csv` | 1,894,350 | 13 | 189.2 MB | one row per player appearance in a game (player x game) | `appearance_id` — UNIQUE | `date`: 2012-07-03 → 2026-06-28 |
| `club_games.csv` | 177,916 | 11 | 14.1 MB | one row per club per game (2 rows per game: home + away) | `game_id + club_id` — UNIQUE | no date column (join `games.csv` for game dates) |
| `clubs.csv` | 796 | 17 | 0.2 MB | one row per club (scraped latest-season roster; see date field `last_season`) | `club_id` — UNIQUE | no date column (join `games.csv` for game dates) |
| `competitions.csv` | 65 | 11 | 0.0 MB | one row per competition (leagues, cups, national teams) | `competition_id` — UNIQUE | no date column (join `games.csv` for game dates) |
| `countries.csv` | 124 | 8 | 0.0 MB | one row per country | `country_id` — UNIQUE | no date column (join `games.csv` for game dates) |
| `game_events.csv` | 1,274,469 | 11 | 170.8 MB | one row per recorded in-game event (goal, card, substitution, shootout) | `game_event_id` — UNIQUE | `date`: 2006-06-09 → 2026-07-06 |
| `game_lineups.csv` | 3,179,016 | 10 | 396.7 MB | one row per player per game per lineup type (starting/substitute) | `game_lineups_id` — UNIQUE | `date`: 2013-07-02 → 2026-07-06 |
| `games.csv` | 88,958 | 23 | 27.6 MB | one row per game | `game_id` — UNIQUE | `date`: 2006-06-09 → 2026-07-06 |
| `national_teams.csv` | 124 | 17 | 0.0 MB | one row per national team | `national_team_id` — UNIQUE | no date column (join `games.csv` for game dates) |
| `players.csv` | 50,149 | 26 | 18.7 MB | one row per player (attributes as of scrape date) | `player_id` — UNIQUE | `date_of_birth`: 1968-07-31 → 2011-02-23; `contract_expiration_date`: 2000-05-31 → 2035-06-30 |
| `player_valuations.csv` | 656,301 | 6 | 37.8 MB | one row per player market-value snapshot (player x date) | `player_id + date` — UNIQUE | `date`: 2000-01-20 → 2026-06-12 |
| `transfers.csv` | 175,165 | 10 | 17.3 MB | one row per transfer event | none (see §3) | `transfer_date`: 1993-07-01 → 2030-06-30 |

Total: 12 files, 873.4 MB on disk. All row counts are exact (full parse by pandas).
Note: `transfers.csv` contains transfer dates up to 2030 (see §12).

---

## 2. Schema per file

dtypes as inferred by pandas 3.0.6 (`read_csv` defaults, chunked for the three big files).
Columns with >20% nulls are flagged. `str` = text, `int64`/`float64` = numeric.

### `appearances.csv` (1,894,350 rows)

| column | dtype | nulls | null rate | >20% null |
|---|---|---:|---:|:--:|
| `appearance_id` | str | 0 | 0.00% |  |
| `game_id` | int64 | 0 | 0.00% |  |
| `player_id` | int64 | 0 | 0.00% |  |
| `player_club_id` | int64 | 0 | 0.00% |  |
| `player_current_club_id` | int64 | 0 | 0.00% |  |
| `date` | str | 0 | 0.00% |  |
| `player_name` | str | 2 | 0.00% |  |
| `competition_id` | str | 0 | 0.00% |  |
| `yellow_cards` | int64 | 0 | 0.00% |  |
| `red_cards` | int64 | 0 | 0.00% |  |
| `goals` | int64 | 0 | 0.00% |  |
| `assists` | int64 | 0 | 0.00% |  |
| `minutes_played` | int64 | 0 | 0.00% |  |

### `club_games.csv` (177,916 rows)

| column | dtype | nulls | null rate | >20% null |
|---|---|---:|---:|:--:|
| `game_id` | int64 | 0 | 0.00% |  |
| `club_id` | int64 | 0 | 0.00% |  |
| `own_goals` | int64 | 0 | 0.00% |  |
| `own_position` | float64 | 50,754 | 28.53% | **YES** |
| `own_manager_name` | str | 1,688 | 0.95% |  |
| `opponent_id` | int64 | 0 | 0.00% |  |
| `opponent_goals` | int64 | 0 | 0.00% |  |
| `opponent_position` | float64 | 50,754 | 28.53% | **YES** |
| `opponent_manager_name` | str | 1,688 | 0.95% |  |
| `hosting` | str | 0 | 0.00% |  |
| `is_win` | int64 | 0 | 0.00% |  |

### `clubs.csv` (796 rows)

| column | dtype | nulls | null rate | >20% null |
|---|---|---:|---:|:--:|
| `club_id` | int64 | 0 | 0.00% |  |
| `club_code` | str | 0 | 0.00% |  |
| `name` | str | 0 | 0.00% |  |
| `domestic_competition_id` | str | 0 | 0.00% |  |
| `total_market_value` | float64 | 796 | 100.00% | **YES** |
| `squad_size` | int64 | 0 | 0.00% |  |
| `average_age` | float64 | 38 | 4.77% |  |
| `foreigners_number` | int64 | 0 | 0.00% |  |
| `foreigners_percentage` | float64 | 60 | 7.54% |  |
| `national_team_players` | int64 | 0 | 0.00% |  |
| `stadium_name` | str | 0 | 0.00% |  |
| `stadium_seats` | int64 | 0 | 0.00% |  |
| `net_transfer_record` | str | 0 | 0.00% |  |
| `coach_name` | str | 393 | 49.37% | **YES** |
| `last_season` | int64 | 0 | 0.00% |  |
| `filename` | str | 0 | 0.00% |  |
| `url` | str | 0 | 0.00% |  |

### `competitions.csv` (65 rows)

| column | dtype | nulls | null rate | >20% null |
|---|---|---:|---:|:--:|
| `competition_id` | str | 0 | 0.00% |  |
| `competition_code` | str | 0 | 0.00% |  |
| `name` | str | 0 | 0.00% |  |
| `sub_type` | str | 0 | 0.00% |  |
| `type` | str | 0 | 0.00% |  |
| `country_id` | int64 | 0 | 0.00% |  |
| `country_name` | str | 12 | 18.46% |  |
| `domestic_league_code` | str | 12 | 18.46% |  |
| `confederation` | str | 0 | 0.00% |  |
| `total_clubs` | float64 | 15 | 23.08% | **YES** |
| `url` | str | 0 | 0.00% |  |

### `countries.csv` (124 rows)

| column | dtype | nulls | null rate | >20% null |
|---|---|---:|---:|:--:|
| `country_id` | int64 | 0 | 0.00% |  |
| `country_name` | str | 0 | 0.00% |  |
| `country_code` | str | 0 | 0.00% |  |
| `confederation` | str | 0 | 0.00% |  |
| `total_clubs` | int64 | 0 | 0.00% |  |
| `total_players` | int64 | 0 | 0.00% |  |
| `average_age` | float64 | 0 | 0.00% |  |
| `url` | str | 0 | 0.00% |  |

### `game_events.csv` (1,274,469 rows)

| column | dtype | nulls | null rate | >20% null |
|---|---|---:|---:|:--:|
| `game_event_id` | str | 0 | 0.00% |  |
| `date` | str | 0 | 0.00% |  |
| `game_id` | int64 | 0 | 0.00% |  |
| `minute` | int64 | 0 | 0.00% |  |
| `type` | str | 0 | 0.00% |  |
| `club_id` | int64 | 0 | 0.00% |  |
| `club_name` | str | 0 | 0.00% |  |
| `player_id` | int64 | 0 | 0.00% |  |
| `description` | str | 93,157 | 7.31% |  |
| `player_in_id` | float64 | 643,922 | 50.52% | **YES** |
| `player_assist_id` | float64 | 1,086,191 | 85.23% | **YES** |

### `game_lineups.csv` (3,179,016 rows)

| column | dtype | nulls | null rate | >20% null |
|---|---|---:|---:|:--:|
| `game_lineups_id` | str | 0 | 0.00% |  |
| `date` | str | 0 | 0.00% |  |
| `game_id` | int64 | 0 | 0.00% |  |
| `player_id` | int64 | 0 | 0.00% |  |
| `club_id` | int64 | 0 | 0.00% |  |
| `player_name` | str | 0 | 0.00% |  |
| `type` | str | 0 | 0.00% |  |
| `position` | str | 3 | 0.00% |  |
| `number` | mixed(object,str) | 0 | 0.00% |  |
| `team_captain` | int64 | 0 | 0.00% |  |

### `games.csv` (88,958 rows)

| column | dtype | nulls | null rate | >20% null |
|---|---|---:|---:|:--:|
| `game_id` | int64 | 0 | 0.00% |  |
| `competition_id` | str | 0 | 0.00% |  |
| `season` | int64 | 0 | 0.00% |  |
| `round` | str | 0 | 0.00% |  |
| `date` | str | 0 | 0.00% |  |
| `home_club_id` | int64 | 0 | 0.00% |  |
| `away_club_id` | int64 | 0 | 0.00% |  |
| `home_club_goals` | int64 | 0 | 0.00% |  |
| `away_club_goals` | int64 | 0 | 0.00% |  |
| `home_club_position` | float64 | 25,377 | 28.53% | **YES** |
| `away_club_position` | float64 | 25,377 | 28.53% | **YES** |
| `home_club_manager_name` | str | 844 | 0.95% |  |
| `away_club_manager_name` | str | 844 | 0.95% |  |
| `stadium` | str | 242 | 0.27% |  |
| `attendance` | float64 | 10,803 | 12.14% |  |
| `referee` | str | 678 | 0.76% |  |
| `url` | str | 0 | 0.00% |  |
| `home_club_formation` | str | 8,200 | 9.22% |  |
| `away_club_formation` | str | 8,073 | 9.08% |  |
| `home_club_name` | str | 86 | 0.10% |  |
| `away_club_name` | str | 36 | 0.04% |  |
| `aggregate` | str | 0 | 0.00% |  |
| `competition_type` | str | 1,214 | 1.36% |  |

### `national_teams.csv` (124 rows)

| column | dtype | nulls | null rate | >20% null |
|---|---|---:|---:|:--:|
| `national_team_id` | int64 | 0 | 0.00% |  |
| `name` | str | 0 | 0.00% |  |
| `team_code` | str | 0 | 0.00% |  |
| `country_id` | int64 | 0 | 0.00% |  |
| `country_name` | str | 0 | 0.00% |  |
| `country_code` | str | 0 | 0.00% |  |
| `confederation` | str | 1 | 0.81% |  |
| `team_image_url` | str | 0 | 0.00% |  |
| `squad_size` | int64 | 0 | 0.00% |  |
| `average_age` | float64 | 0 | 0.00% |  |
| `foreigners_number` | int64 | 0 | 0.00% |  |
| `foreigners_percentage` | float64 | 8 | 6.45% |  |
| `total_market_value` | float64 | 4 | 3.23% |  |
| `coach_name` | float64 | 124 | 100.00% | **YES** |
| `fifa_ranking` | int64 | 0 | 0.00% |  |
| `last_season` | int64 | 0 | 0.00% |  |
| `url` | str | 0 | 0.00% |  |

### `players.csv` (50,149 rows)

| column | dtype | nulls | null rate | >20% null |
|---|---|---:|---:|:--:|
| `player_id` | int64 | 0 | 0.00% |  |
| `first_name` | str | 3,164 | 6.31% |  |
| `last_name` | str | 0 | 0.00% |  |
| `name` | str | 0 | 0.00% |  |
| `last_season` | int64 | 0 | 0.00% |  |
| `current_club_id` | int64 | 0 | 0.00% |  |
| `player_code` | str | 0 | 0.00% |  |
| `country_of_birth` | str | 5,885 | 11.73% |  |
| `city_of_birth` | str | 5,608 | 11.18% |  |
| `country_of_citizenship` | str | 269 | 0.54% |  |
| `date_of_birth` | str | 49 | 0.10% |  |
| `sub_position` | str | 586 | 1.17% |  |
| `position` | str | 0 | 0.00% |  |
| `foot` | str | 5,893 | 11.75% |  |
| `height_in_cm` | float64 | 4,365 | 8.70% |  |
| `contract_expiration_date` | str | 18,569 | 37.03% | **YES** |
| `agent_name` | str | 23,296 | 46.45% | **YES** |
| `image_url` | str | 0 | 0.00% |  |
| `international_caps` | float64 | 30,793 | 61.40% | **YES** |
| `international_goals` | float64 | 30,793 | 61.40% | **YES** |
| `current_national_team_id` | float64 | 46,889 | 93.50% | **YES** |
| `url` | str | 0 | 0.00% |  |
| `current_club_domestic_competition_id` | str | 2,986 | 5.95% |  |
| `current_club_name` | str | 2,986 | 5.95% |  |
| `market_value_in_eur` | float64 | 8,621 | 17.19% |  |
| `highest_market_value_in_eur` | float64 | 8,621 | 17.19% |  |

### `player_valuations.csv` (656,301 rows)

| column | dtype | nulls | null rate | >20% null |
|---|---|---:|---:|:--:|
| `player_id` | int64 | 0 | 0.00% |  |
| `date` | str | 0 | 0.00% |  |
| `market_value_in_eur` | int64 | 0 | 0.00% |  |
| `current_club_name` | str | 0 | 0.00% |  |
| `current_club_id` | int64 | 0 | 0.00% |  |
| `player_club_domestic_competition_id` | str | 92,973 | 14.17% |  |

### `transfers.csv` (175,165 rows)

| column | dtype | nulls | null rate | >20% null |
|---|---|---:|---:|:--:|
| `player_id` | int64 | 0 | 0.00% |  |
| `transfer_date` | str | 0 | 0.00% |  |
| `transfer_season` | str | 0 | 0.00% |  |
| `from_club_id` | int64 | 0 | 0.00% |  |
| `to_club_id` | int64 | 0 | 0.00% |  |
| `from_club_name` | str | 0 | 0.00% |  |
| `to_club_name` | str | 0 | 0.00% |  |
| `transfer_fee` | float64 | 61,526 | 35.12% | **YES** |
| `market_value_in_eur` | float64 | 68,160 | 38.91% | **YES** |
| `player_name` | str | 0 | 0.00% |  |


---

## 3. Duplicates

Full-row duplicate scan and key-level duplicate scan per file (exact, full parse with `dtype=str`).

| file | full-row dups | key checked | dup rows on key |
|---|---:|---|---:|
| `appearances.csv` | 0 | `appearance_id` | 0 |
|  |  | `player_id + game_id` | 0 |
| `club_games.csv` | 0 | `game_id + club_id` | 0 |
|  |  | `game_id` | 88,958 |
| `clubs.csv` | 0 | `club_id` | 0 |
| `competitions.csv` | 0 | `competition_id` | 0 |
| `countries.csv` | 0 | `country_id` | 0 |
| `game_events.csv` | 0 | `game_event_id` | 0 |
|  |  | `game_id + player_id + type + minute` | 906 |
| `game_lineups.csv` | 0 | `game_lineups_id` | 0 |
|  |  | `game_id + player_id` | 12 |
|  |  | `game_id + player_id + type` | 12 |
| `games.csv` | 0 | `game_id` | 0 |
| `national_teams.csv` | 0 | `national_team_id` | 0 |
| `players.csv` | 0 | `player_id` | 0 |
|  |  | `name` | 1,324 |
| `player_valuations.csv` | 0 | `player_id + date` | 0 |
| `transfers.csv` | 0 | `player_id + transfer_date + from_club_id + to_club_id` | 0 |
|  |  | `player_id + transfer_date` | 118 |

Findings:

- No full-row duplicates anywhere in the dataset.
- `appearances`: `(player_id, game_id)` is unique — grain is truly one row per player per game.
- `game_lineups`: 12 extra rows share `(game_id, player_id)` — a player listed twice in the same game's lineups.
- `game_events`: 906 rows share `(game_id, player_id, type, minute)` — multiple events of the same type in the same minute (e.g. goal + second yellow); `game_event_id` itself is unique.
- `players`: 1,324 rows share a `name` with another row — different `player_id`s with identical names; never join on name, only on `player_id`.
- `transfers`: 118 rows share `(player_id, transfer_date)` (e.g. two moves on the same day); the 4-column tuple is unique, so there is no single-column or 2-column PK.
- `player_valuations`: `(player_id, date)` is unique — no duplicate snapshots on the same date.

---

## 4. Numeric summaries

Every numeric column of interest. Zeros/negatives counted on non-null values.

### `appearances.csv`

| column | n | nulls | min | max | mean | median | p25 | p75 | p99 | zeros | negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `yellow_cards` | 1,894,350 | 0 | 0 | 2 | 0.1449 | 0 | 0 | 0 | 1 | 1,626,661 | 0 |
| `red_cards` | 1,894,350 | 0 | 0 | 1 | 0.003478 | 0 | 0 | 0 | 0 | 1,887,762 | 0 |
| `goals` | 1,894,350 | 0 | 0 | 6 | 0.09525 | 0 | 0 | 0 | 1 | 1,732,802 | 0 |
| `assists` | 1,894,350 | 0 | 0 | 6 | 0.07496 | 0 | 0 | 0 | 1 | 1,762,581 | 0 |
| `minutes_played` | 1,894,350 | 0 | 0 | 148 | 68.52 | 90 | 45 | 90 | 90 | 3 | 0 |

### `club_games.csv`

| column | n | nulls | min | max | mean | median | p25 | p75 | p99 | zeros | negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `own_goals` | 177,916 | 0 | 0 | 19 | 1.463 | 1 | 0 | 2 | 6 | 48,442 | 0 |
| `own_position` | 127,162 | 50,754 | 1 | 21 | 9.199 | 9 | 5 | 13 | 20 | 0 | 0 |
| `opponent_goals` | 177,916 | 0 | 0 | 19 | 1.463 | 1 | 0 | 2 | 6 | 48,442 | 0 |
| `opponent_position` | 127,162 | 50,754 | 1 | 21 | 9.199 | 9 | 5 | 13 | 20 | 0 | 0 |
| `is_win` | 177,916 | 0 | 0 | 1 | 0.3915 | 0 | 0 | 1 | 1 | 108,260 | 0 |

### `clubs.csv`

| column | n | nulls | min | max | mean | median | p25 | p75 | p99 | zeros | negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `total_market_value` | all null | - | - | - | - | - | - | - | - | - | - |
| `squad_size` | 796 | 0 | 0 | 50 | 26.78 | 28 | 25 | 31 | 42 | 42 | 0 |
| `average_age` | 758 | 38 | 0 | 30.1 | 25.46 | 25.6 | 24.5 | 26.7 | 29.2 | 4 | 0 |
| `foreigners_number` | 796 | 0 | 0 | 36 | 10.55 | 10 | 5 | 15 | 27 | 60 | 0 |
| `foreigners_percentage` | 736 | 60 | 2.4 | 100 | 40.04 | 39.4 | 24 | 54.67 | 84.53 | 0 | 0 |
| `national_team_players` | 796 | 0 | 0 | 24 | 3.923 | 2 | 0 | 6 | 20 | 201 | 0 |
| `stadium_seats` | 796 | 0 | 0 | 87,523 | 24,269.8 | 20,019 | 10,800 | 32,290.2 | 76,005 | 1 | 0 |
| `net_transfer_record (parsed from string like '+5.90m')` | 449 | 347 | -251,200,000 | 144,000,000 | 389,443.2 | 2,450,000 | -3,620,000 | 6,900,000 | 80,117,600 | 0 | 166 |

### `competitions.csv`

| column | n | nulls | min | max | mean | median | p25 | p75 | p99 | zeros | negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `total_clubs` | 50 | 15 | 10 | 30 | 17.16 | 18 | 16 | 19.5 | 30 | 0 | 0 |

### `countries.csv`

| column | n | nulls | min | max | mean | median | p25 | p75 | p99 | zeros | negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `total_clubs` | 124 | 0 | 6 | 36 | 14.24 | 14 | 10.75 | 16 | 30 | 0 | 0 |
| `total_players` | 124 | 0 | 1 | 921 | 405 | 389 | 300.8 | 490.2 | 906.5 | 0 | 0 |
| `average_age` | 124 | 0 | 22.7 | 31.8 | 26.23 | 26.2 | 25.48 | 27.02 | 29.65 | 0 | 0 |

### `game_events.csv`

| column | n | nulls | min | max | mean | median | p25 | p75 | p99 | zeros | negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `minute` | 1,274,469 | 0 | -1 | 120 | 62.09 | 67 | 46 | 80 | 90 | 0 | 17,575 |

### `game_lineups.csv`

| column | n | nulls | min | max | mean | median | p25 | p75 | p99 | zeros | negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `number` | 3,153,318 | 25,698 | 1 | 880 | 21.73 | 17 | 8 | 27 | 97 | 0 | 0 |
| `team_captain` | 3,179,016 | 0 | 0 | 1 | 0.04708 | 0 | 0 | 0 | 1 | 3,029,354 | 0 |

### `games.csv`

| column | n | nulls | min | max | mean | median | p25 | p75 | p99 | zeros | negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `home_club_goals` | 88,958 | 0 | 0 | 15 | 1.597 | 1 | 1 | 2 | 6 | 20,940 | 0 |
| `away_club_goals` | 88,958 | 0 | 0 | 19 | 1.328 | 1 | 0 | 2 | 6 | 27,502 | 0 |
| `home_club_position` | 63,581 | 25,377 | 1 | 21 | 9.11 | 9 | 5 | 13 | 20 | 0 | 0 |
| `away_club_position` | 63,581 | 25,377 | 1 | 21 | 9.289 | 9 | 5 | 14 | 20 | 0 | 0 |
| `attendance` | 78,155 | 10,803 | 1 | 99,354 | 18,282.5 | 12,350 | 4,418.5 | 26,353 | 75,000 | 0 | 0 |

### `national_teams.csv`

| column | n | nulls | min | max | mean | median | p25 | p75 | p99 | zeros | negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `squad_size` | 124 | 0 | 19 | 33 | 25.31 | 26 | 24 | 26 | 29.77 | 0 | 0 |
| `average_age` | 124 | 0 | 21 | 30.5 | 26.87 | 26.9 | 26.1 | 28 | 30.33 | 0 | 0 |
| `foreigners_number` | 124 | 0 | 0 | 30 | 14.07 | 14.5 | 7 | 22 | 26.77 | 8 | 0 |
| `foreigners_percentage` | 116 | 8 | 3.8 | 100 | 58.96 | 59.3 | 34.6 | 88.5 | 100 | 0 | 0 |
| `total_market_value` | 120 | 4 | 350,000 | 947,000,000 | 130,891,125.4 | 34,375,000 | 8,132,500 | 193,550,003 | 905,267,009.7 | 0 | 0 |
| `fifa_ranking` | 124 | 0 | 1 | 211 | 79.67 | 68.5 | 31.75 | 123.2 | 201.8 | 0 | 0 |

### `players.csv`

| column | n | nulls | min | max | mean | median | p25 | p75 | p99 | zeros | negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `height_in_cm` | 45,784 | 4,365 | 17 | 210 | 182 | 182 | 177 | 187 | 197 | 0 | 0 |
| `international_caps` | 19,356 | 30,793 | 0 | 233 | 11.37 | 4 | 1 | 12 | 94 | 2,410 | 0 |
| `international_goals` | 19,356 | 30,793 | 0 | 146 | 1.183 | 0 | 0 | 1 | 16 | 13,426 | 0 |
| `market_value_in_eur` | 41,528 | 8,621 | 10,000 | 200,000,000 | 1,511,049.3 | 275,000 | 100,000 | 700,000 | 25,000,000 | 0 | 0 |
| `highest_market_value_in_eur` | 41,528 | 8,621 | 10,000 | 200,000,000 | 3,450,773.5 | 750,000 | 300,000 | 2,500,000 | 45,000,000 | 0 | 0 |

### `player_valuations.csv`

| column | n | nulls | min | max | mean | median | p25 | p75 | p99 | zeros | negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `market_value_in_eur` | 656,301 | 0 | 0 | 200,000,000 | 2,290,092.7 | 500,000 | 200,000 | 1,500,000 | 32,000,000 | 1 | 0 |

### `transfers.csv`

| column | n | nulls | min | max | mean | median | p25 | p75 | p99 | zeros | negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `transfer_fee` | 113,639 | 61,526 | 0 | 222,000,000 | 739,836 | 0 | 0 | 0 | 18,000,000 | 96,085 | 0 |
| `market_value_in_eur` | 107,005 | 68,160 | 10,000 | 180,000,000 | 1,753,553.9 | 425,000 | 200,000 | 1,200,000 | 22,000,000 | 0 | 0 |

`clubs.net_transfer_record` is stored as a signed string (e.g. `+€5.90m`, `€-25.00m`);
the summary row parses it to EUR (x1e6). `clubs.total_market_value` is entirely null in this
snapshot of the dataset.

---

## 5. Target analysis: market_value_in_eur

### Distribution shape

| distribution | n | min | p1 | p5 | p25 | p50 | p75 | p90 | p95 | p99 | max | mean | skew | zeros | negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| player_valuations.market_value_in_eur (all snapshots) | 656,301 | €0 | €25,000 | €50,000 | €200,000 | €500,000 | €1,500,000 | €5,000,000 | €10,000,000 | €32,000,000 | €200,000,000 | €2,290,093 | 8.70 | 1 | 0 |
| players.market_value_in_eur (current snapshot) | 41,528 | €10,000 | €25,000 | €50,000 | €100,000 | €275,000 | €700,000 | €2,500,000 | €6,000,000 | €25,000,000 | €200,000,000 | €1,511,049 | 11.75 | 0 | 0 |
| players.highest_market_value_in_eur (post-hoc; leakage) | 41,528 | €10,000 | €25,000 | €50,000 | €300,000 | €750,000 | €2,500,000 | €8,000,000 | €15,000,000 | €45,000,000 | €200,000,000 | €3,450,773 | 7.45 | 0 | 0 |

- The raw target is heavily right-skewed (skew 8.70 on all valuation snapshots; 11.75 on players' current values) with a heavy tail: max is €200,000,000 vs median €500,000. The top 1% of snapshots hold 23.15% of total valuation mass.
- No negative values anywhere. Exactly 1 zero in all of `player_valuations` (0 in `players`), so zeros are not a modeling concern.

### Log-transform diagnostic (all valuation snapshots, `log1p`)

- raw skew 8.70 → log1p skew **0.43** (near-symmetric)
- log1p mean 13.28, std 1.54

**Verdict: log-transform is required.** Raw EUR values are unusable as a regression target for
most losses (skew ~8.7, 4 orders of magnitude between p50 and p99). `log1p` brings skew under
0.5; train in log space and report metrics both in log space and back-transformed EUR.

### Valuation coverage and history depth

- Players in `players.csv`: 50,149;
  **with** valuation history: 41,528;
  **without** any snapshot: 8,621 (17.19% of players).
- Every valuation `player_id` resolves to `players.csv` (0 orphans) — the valuation table is a strict subset of known players.

| snapshots per player | players |
|---|---:|
| 1 | 1,063 |
| 2-5 | 5,940 |
| 6-10 | 7,434 |
| 11-20 | 14,294 |
| 21-50 | 12,779 |
| >50 | 18 |

min 1, median 15, mean 15.8, p90 30, p99 41, max 57.

- `players.market_value_in_eur` equals the **last** valuation snapshot for 100.00% of the 41,528 comparable players, but equals the all-time max for only 29.95% — it is a current snapshot, not a max-career figure. It is post-hoc w.r.t. any past prediction date.

---

## 6. Transfer fee specifics

`transfer_fee` over all 175,165 transfers:

| category | count | share |
|---|---:|---:|
| null (fee not recorded) | 61,526 | 35.12% |
| exactly 0 (free / undisclosed) | 96,085 | 54.85% |
| positive (recorded fee) | 17,554 | 10.02% |
| negative | 0 | 0.00% |

- Of the 96,085 zero-fee rows: 70,695 carry a positive market value and 25,390 have no market value at all. A zero fee therefore conflates genuinely free transfers with undisclosed fees — it is a censored value, not a price of 0.
- Smallest recorded positive fee: €400; 7 fees below €1k, 55 below €10k, none equal to €1 — no €1 sentinel pattern.
- `market_value_in_eur` inside transfers: 68,160 null, 0 zero, 0 negative.

### Fee vs market value at transfer date (rows with fee > 0 and mv > 0)

n = 16,442; ratio = fee / market_value:

| p1 | p5 | p25 | p50 | p75 | p90 | p95 | p99 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.07 | 0.18 | 0.53 | 0.94 | 1.50 | 2.78 | 4.43 | 14.00 |

- Median fee is 0.94x market value — fees roughly track valuations at the median.
- 2,488 transfers at >2x market value (638 at >5x); 3,583 below half of market value (244 below a tenth).

**Usability verdict:** fee-based supervision is only possible on the 10.02% of rows with a recorded positive fee; treating 0 as a real price
would corrupt any target built from it. Null-fee and zero-fee rows should be excluded from fee regression
or handled as censored observations.

---

## 7. Categoricals

### `players.csv`

| column | distinct | nulls | top values (count) |
|---|---:|---:|---|
| `position` | 5 | 0 | Defender (15,961), Midfield (14,272), Attack (13,502), Goalkeeper (5,828), Missing (586) |
| `sub_position` | 13 | 586 | Centre-Back (8,766), Centre-Forward (6,749), Goalkeeper (5,828), Central Midfield (5,498), Defensive Midfield (4,123) |
| `foot` | 3 | 5,893 | right (31,445), left (11,000), both (1,811) |
| `last_season` | 14 | 0 | 2025 (22,292), 2024 (6,075), 2023 (2,092), 2018 (2,065), 2013 (2,061) |

### `appearances.csv`

| column | distinct | nulls | top values (count) |
|---|---:|---:|---|
| `competition_id` | 48 | 0 | IT1 (155,187), ES1 (153,877), GB1 (149,751), FR1 (143,395), TR1 (132,464) |

### `games.csv`

| column | distinct | nulls | top values (count) |
|---|---:|---:|---|
| `competition_id` | 70 | 0 | GB1 (5,320), ES1 (5,320), IT1 (5,320), FR1 (4,997), TR1 (4,618) |
| `season` | 18 | 0 | 2024 (10,036), 2025 (9,598), 2022 (6,008), 2023 (5,951), 2021 (5,939) |
| `competition_type` | 5 | 1,214 | domestic_league (63,382), domestic_cup (12,904), other (7,599), international_cup (3,117), national_team_competition (742) |

### `game_events.csv`

| column | distinct | nulls | top values (count) |
|---|---:|---:|---|
| `type` | 4 | 0 | Substitutions (631,339), Cards (381,753), Goals (247,803), Shootout (13,574) |

### `game_lineups.csv`

| column | distinct | nulls | top values (count) |
|---|---:|---:|---|
| `type` | 2 | 0 | starting_lineup (1,780,759), substitutes (1,398,257) |
| `position` | 18 | 3 | Centre-Back (551,970), Centre-Forward (394,661), Goalkeeper (357,844), Central Midfield (329,361), Defensive Midfield (279,364) |

### `transfers.csv`

| column | distinct | nulls | top values (count) |
|---|---:|---:|---|
| `transfer_season` | 35 | 0 | 23/24 (17,379), 24/25 (16,686), 22/23 (16,386), 25/26 (15,676), 21/22 (15,045) |

### `player_valuations.csv`

| column | distinct | nulls | top values (count) |
|---|---:|---:|---|
| `player_club_domestic_competition_id` | 32 | 92,973 | IT1 (50,413), TR1 (47,666), ES1 (37,561), L1 (37,049), GB1 (33,748) |

### `competitions.csv`

| column | distinct | nulls | top values (count) |
|---|---:|---:|---|
| `type` | 5 | 0 | domestic_league (31), other (16), domestic_cup (10), national_team_competition (5), international_cup (3) |
| `sub_type` | 16 | 0 | first_tier (31), domestic_cup (10), domestic_super_cup (9), play_off (3), afc_asian_cup (1) |
| `confederation` | 5 | 0 | europa (53), asien (5), amerika (5), afrika (1), fifa (1) |

### `club_games.csv`

| column | distinct | nulls | top values (count) |
|---|---:|---:|---|
| `hosting` | 2 | 0 | Home (88,958), Away (88,958) |
| `is_win` | 2 | 0 | 0 (108,260), 1 (69,656) |

Note: `appearances.csv` covers 48 competitions while `games.csv` covers 70 — 22 competitions
have games but (nearly) no recorded appearances; see orphan `competition_id` in §8.

---

## 8. Referential integrity

Orphans = non-null key values with no matching row in the dimension table. Rate is over non-null values.

| fact column → dimension | non-null | null | orphans | orphan rate | example orphan keys |
|---|---:|---:|---:|---:|---|
| `appearances.csv`: `competition_id -> competitions` | 1,894,350 | 0 | 14,200 | 0.75% | CGB, KLUB, POCP |
| `appearances.csv`: `game_id -> games` | 1,894,350 | 0 | 0 | 0.00% | - |
| `appearances.csv`: `player_club_id -> clubs` | 1,894,350 | 0 | 11,062 | 0.58% | 1020, 1035, 1042 |
| `appearances.csv`: `player_current_club_id -> clubs` | 1,894,350 | 0 | 24,431 | 1.29% | 1008, 1037, 10482 |
| `appearances.csv`: `player_id -> players` | 1,894,350 | 0 | 2 | 0.00% | 380365 |
| `club_games.csv`: `club_id -> clubs` | 177,916 | 0 | 24,060 | 13.52% | 3437, 3441, 3449 |
| `club_games.csv`: `game_id -> games` | 177,916 | 0 | 0 | 0.00% | - |
| `club_games.csv`: `opponent_id -> clubs` | 177,916 | 0 | 24,060 | 13.52% | 3437, 3449, 3505 |
| `games.csv`: `away_club_id -> clubs` | 88,958 | 0 | 11,242 | 12.64% | 3299, 3441, 3503 |
| `games.csv`: `competition_id -> competitions` | 88,958 | 0 | 1,214 | 1.36% | CGB, COL1, KLUB |
| `games.csv`: `home_club_id -> clubs` | 88,958 | 0 | 12,818 | 14.41% | 3262, 3379, 3437 |
| `player_valuations.csv`: `current_club_id -> clubs` | 656,301 | 0 | 92,973 | 14.17% | 466, 6189, 73 |
| `player_valuations.csv`: `player_id -> players` | 656,301 | 0 | 0 | 0.00% | - |
| `transfers.csv`: `from_club_id -> clubs` | 175,165 | 0 | 109,676 | 62.61% | 35387, 41061, 541 |
| `transfers.csv`: `player_id -> players` | 175,165 | 0 | 0 | 0.00% | - |
| `transfers.csv`: `to_club_id -> clubs` | 175,165 | 0 | 92,746 | 52.95% | 123, 25444, 46292 |
| `game_events.csv`: `club_id -> clubs` | 1,274,469 | 0 | 169,317 | 13.29% | 11177, 119, 12469 |
| `game_events.csv`: `game_id -> games` | 1,274,469 | 0 | 0 | 0.00% | - |
| `game_events.csv`: `player_id -> players` | 1,274,469 | 0 | 128,274 | 10.06% | 1000672, 132677, 1335581 |
| `game_lineups.csv`: `club_id -> clubs` | 3,179,016 | 0 | 386,777 | 12.17% | 1028, 10284, 10854 |
| `game_lineups.csv`: `game_id -> games` | 3,179,016 | 0 | 0 | 0.00% | - |
| `game_lineups.csv`: `player_id -> players` | 3,179,016 | 0 | 315,555 | 9.93% | 1060188, 106246, 125917 |
| `players.csv`: `current_club_id -> clubs` | 50,149 | 0 | 2,986 | 5.95% | 123, 184, 2433 |
| `players.csv`: `current_national_team_id -> national_teams` | 3,260 | 46,889 | 106 | 3.25% | 14161.0, 32364.0, 3591.0 |

Findings:

- `game_id` integrity is perfect everywhere: all appearances, events, lineups and club_games resolve to `games.csv`.
- `players.csv` is nearly complete as a player dimension for event tables: ~10% of game_events and game_lineups player_ids are orphans — players never profiled by Transfermarkt (mostly lower-division). Appearances, valuations and transfers player_ids are fully (or nearly) covered (2 orphans in appearances).
- **`clubs.csv` is NOT a complete club dimension.** It holds only the 796 clubs from the scraped latest-season rosters; historical/defunct clubs are missing. Orphan rates: transfers from_club 62.6%, transfers to_club 52.9%, player_valuations current_club 14.2%, game_lineups club 12.2%, games home_club 14.4%. Any club-level join must tolerate missing clubs (or use club names as fallback).
- `appearances.competition_id`: 14,200 orphans (0.75%) — competitions with games but absent from `competitions.csv`.
- `players.current_national_team_id`: 106 of 3,258 non-null values orphaned against `national_teams.csv`.

---

## 9. Temporal coverage

### Date ranges

| table | column | min | max | future-dated rows |
|---|---|---|---|---:|
| `appearances` | date | 2012-07-03 | 2026-06-28 | 0 |
| `games` | date | 2006-06-09 | 2026-07-06 | 0 |
| `game_events` | date | 2006-06-09 | 2026-07-06 | 0 |
| `game_lineups` | date | 2013-07-02 | 2026-07-06 | 0 rows (checked) |
| `player_valuations` | date | 2000-01-20 | 2026-06-12 | 0 |
| `transfers` | transfer_date | 1993-07-01 | 2030-06-30 | **475** |

### Transfers per season

| transfer_season | transfers |
|---|---:|
| 00/01 | 48 |
| 01/02 | 100 |
| 02/03 | 138 |
| 03/04 | 185 |
| 04/05 | 344 |
| 05/06 | 550 |
| 06/07 | 791 |
| 07/08 | 1,170 |
| 08/09 | 1,469 |
| 09/10 | 2,028 |
| 10/11 | 2,537 |
| 11/12 | 3,383 |
| 12/13 | 4,055 |
| 13/14 | 5,048 |
| 14/15 | 6,166 |
| 15/16 | 7,353 |
| 16/17 | 8,495 |
| 17/18 | 10,125 |
| 18/19 | 11,761 |
| 19/20 | 12,800 |
| 20/21 | 13,647 |
| 21/22 | 15,045 |
| 22/23 | 16,386 |
| 23/24 | 17,379 |
| 24/25 | 16,686 |
| 25/26 | 15,676 |
| 26/27 | 1,706 |
| 27/28 | 13 |
| 93/94 | 2 |
| 94/95 | 4 |
| 95/96 | 4 |
| 96/97 | 6 |
| 97/98 | 9 |
| 98/99 | 24 |
| 99/00 | 32 |

### Games per season

| season | games | min date | max date |
|---|---:|---|---|
| 2005 | 64 | 2006-06-09 | 2006-07-09 |
| 2007 | 31 | 2008-06-07 | 2008-06-29 |
| 2009 | 64 | 2010-06-11 | 2010-07-11 |
| 2011 | 31 | 2012-06-08 | 2012-07-01 |
| 2012 | 5,700 | 2012-07-03 | 2013-06-01 |
| 2013 | 5,826 | 2013-07-02 | 2014-07-13 |
| 2014 | 5,836 | 2014-07-01 | 2015-06-07 |
| 2015 | 5,759 | 2015-06-30 | 2016-07-10 |
| 2016 | 5,699 | 2016-06-28 | 2017-06-03 |
| 2017 | 5,660 | 2017-06-27 | 2018-07-15 |
| 2018 | 5,723 | 2018-06-26 | 2019-06-01 |
| 2019 | 5,469 | 2019-06-25 | 2021-04-03 |
| 2020 | 5,564 | 2020-08-01 | 2021-07-11 |
| 2021 | 5,939 | 2021-06-22 | 2022-12-18 |
| 2022 | 6,008 | 2022-06-21 | 2024-02-25 |
| 2023 | 5,951 | 2023-06-27 | 2024-08-28 |
| 2024 | 10,036 | 2024-01-12 | 2025-12-07 |
| 2025 | 9,598 | 2021-09-22 | 2026-07-06 |

### Valuation snapshots per calendar year

| year | snapshots |
|---|---:|
| 2000 | 1 |
| 2001 | 1 |
| 2003 | 2 |
| 2004 | 2,305 |
| 2005 | 2,439 |
| 2006 | 2,673 |
| 2007 | 5,617 |
| 2008 | 9,305 |
| 2009 | 12,067 |
| 2010 | 13,795 |
| 2011 | 17,788 |
| 2012 | 19,714 |
| 2013 | 22,636 |
| 2014 | 23,707 |
| 2015 | 30,479 |
| 2016 | 34,653 |
| 2017 | 35,923 |
| 2018 | 41,097 |
| 2019 | 46,088 |
| 2020 | 48,749 |
| 2021 | 58,412 |
| 2022 | 59,564 |
| 2023 | 57,576 |
| 2024 | 45,376 |
| 2025 | 45,482 |
| 2026 | 20,852 |

### Valuation snapshots vs transfer dates

- 2.51% of transfers have **no** valuation snapshot for the player at all.
- Nearest snapshot to the transfer date: median gap 62 days, p90 1135 days.
- 7.01% within 7 days, 29.33% within 30 days, 59.02% within 90 days.
- Snapshot within 365 days BEFORE the transfer: 58.77%; within 365 days AFTER: 67.68%; **both (bracketing): 53.02%**.

Conclusion: snapshots are sparse (Transfermarkt updates valuations irregularly, ~15 per player median over
26 years). Transfer-date market values must be approximated by nearest-snapshot interpolation, and the
±90-day window covers only ~59% of transfers — targets aligned to transfer dates will drop or interpolate
the rest.

---

## 10. Leakage watchlist

Columns that encode post-hoc or outcome information and must NOT feed a model that predicts
market value at a past date. The governing rule: **everything in `players.csv` and `clubs.csv` is
scraped-state as of the dataset build (late 2025/2026)**; only the dated tables (`appearances`,
`player_valuations`, `transfers`, `games`, `game_events`, `game_lineups`) can be joined as-of a
prediction date safely.

| column | why it leaks |
|---|---|
| `players.highest_market_value_in_eur` | maximum value over the player's whole future career; directly reveals the outcome trajectory |
| `players.market_value_in_eur` | current (latest) snapshot — equals the last valuation row for 100% of players; post-hoc for any past target date |
| `players.last_season` | season in which the player was last active — known only after the fact |
| `players.current_club_id` / `current_club_name` / `current_club_domestic_competition_id` | club at scrape time, not at prediction time |
| `players.current_national_team_id`, `international_caps`, `international_goals` | career totals as of scrape date, with no timeline — they include caps/goals earned after any past prediction date |
| `players.contract_expiration_date` | can reveal the next club move (e.g. free transfer) before it is public |
| `appearances.player_current_club_id` | player's club at scrape time; for old appearances this is post-hoc (use `player_club_id`, the club at game time) |
| `transfers.transfer_fee`, `transfers.market_value_in_eur` | realized outcome at/after the transfer; a feature for later targets but leakage for predicting value BEFORE the transfer |
| `games.home_club_goals` / `away_club_goals`, `club_games.is_win`, `own_goals`/`opponent_goals` | match outcomes; only usable for windows strictly before the prediction date |
| `club_games.own_position` / `opponent_position` | league position updated through the season; the final value encodes the rest of the season |
| `clubs.net_transfer_record`, `clubs.total_market_value`, `clubs.last_season`, `clubs.coach_name` | season aggregates computed after the season ends |
| `player_valuations.current_club_id` / `current_club_name` | safe ONLY because the row is a dated snapshot (club as-of that date); do not confuse with players.csv current_* |
| `games.round`, `games.aggregate` | cup-round labels can encode how far a team progressed in the competition |

Safe-by-construction features: attributes dated on or before the prediction date (appearances,
lineups, events, valuation snapshots, transfer history joined strictly as-of).

---

## 11. Aggregation feasibility

### What CAN be built (per player, rolling windows or per season)

- From `appearances` (1,894,350 rows): appearances count, `minutes_played` sum/mean, `goals`,
  `assists`, `yellow_cards`, `red_cards`; derived rates such as goals-per-90 / assists-per-90
  (3 rows have minutes > 130 and 3 rows have 0 minutes — negligible, filterable).
- From `game_lineups` (3,179,016 rows): starts (`type = starting_lineup`, 1,780,759 rows) vs
  substitute appearances (1,398,257), `position` history (18 values, e.g. Centre-Back, Central
  Midfield), shirt `number` (with 25,698 `'-'` placeholders), `team_captain` flag (captaincy frequency).
- From `game_events` (1,274,469 rows): goals with exact `minute` (time-weighted goal minutes),
  cards by type, substitutions (with `player_in_id` — who replaced whom), `player_assist_id`
  (assist credit on goal events), shootout events.
- From `club_games` (177,916 rows): team-level results (`own_goals`, `is_win`, `hosting`) and
  opponent strength — usable as team-context features behind a player.
- From `games` (88,958 rows): competition, season, round, attendance, formations, manager names.
- Static player attributes: height, foot, position/sub_position, date of birth (=> age at any
  prediction date), country of birth/citizenship. International caps/goals exist only as
  scrape-date career totals (no timeline) — usable only with the leakage caveat in §10.

### Advanced scouting metrics: NOT PRESENT

`game_events.type` has exactly **four** values: Cards, Goals, Shootout, Substitutions
(counts in §7). `game_events` columns are: game_event_id, date, game_id, minute, type, club_id,
club_name, player_id, description, player_in_id, player_assist_id. `game_lineups` columns carry
only lineup/position/number/captain. `appearances` carries only cards/goals/assists/minutes.

**The dataset contains NO key passes, NO recoveries, NO dribbles, NO shots (except shootout
events), NO pass counts, NO xG/xA, NO progressive carries, NO tracking data.** The project
charter's example mentioning 'key passes and recoveries' is not supported by this dataset; the
paper/system wording must be corrected to describe features that are actually derivable:
goals, assists, cards, minutes, starts, positions, captaincy, age, physical attributes, and
team context. Any richer metric would require a different data source (e.g. StatsBomb/Opta).

---

## 12. Data quality issues found

| issue | file | count | note |
|---|---|---:|---|
| future-dated transfers (max 2030-06-30) | transfers.csv | 475 | mostly contract-expiry-style entries dated 2027-2030 |
| transfer_season disagrees with year(transfer_date) | transfers.csv | 181 | season start-year vs date year |
| self-transfers (from == to club) | transfers.csv | 8 | club_id identical on both sides |
| from_club_name differs from clubs.name for same id | transfers.csv | 47,948 | historical club names at transfer time; clubs.csv only has 796 clubs |
| to_club_name differs from clubs.name for same id | transfers.csv | 60,629 | same as above |
| player_name vs players.name mismatches | transfers.csv | 0 | 0 of 175,165 compared — names are consistent |
| negative event minutes | game_events.csv | 17,575 | minute < 0 (e.g. halftime-whistle markers) |
| non-numeric shirt number ('-') | game_lineups.csv | 25,698 | makes `number` a mixed-type column |
| shirt number outside 1-99 | game_lineups.csv | 807 | after numeric coercion |
| same player twice in one game's lineups | game_lineups.csv | 12 | extra rows on (game_id, player_id) |
| null attendance | games.csv | 10,803 | 12.14% of games |
| goals sum > 15 in a game | games.csv | 107 | extreme results (data-entry or real routs) |
| minutes_played > 130 | appearances.csv | 3 | beyond max possible playing time |
| minutes_played == 0 | appearances.csv | 3 | none of them have goals/assists |
| null player_name | appearances.csv | 2 | cosmetic |
| zero market value snapshot | player_valuations.csv | 1 | only one in the dataset |
| duplicate (player_id, date) snapshots | player_valuations.csv | 0 | none — snapshot table is clean |
| null date_of_birth | players.csv | 49 | blocks age features |
| age at last_season > 45 | players.csv | 1 | implausible |
| height < 150 cm | players.csv | 13 | implausible (or data entry) |
| international_goals > international_caps | players.csv | 28 | logically impossible |
| duplicate player names | players.csv | 1,324 | distinct player_ids sharing a name — name joins are unsafe |
| null coach_name | clubs.csv | 393 | 49.37% of clubs |
| total_market_value entirely null | clubs.csv | all | column unusable in this snapshot |
| player_id not in players | appearances.csv | 2 | trivial |
| club ids not in clubs.csv (historical clubs) | transfers.csv etc. | from_club 109,676, to_club 92,746 | clubs.csv is last-season-only — see §8 |

**Overall:** the dataset is unusually clean for its size — no full-row duplicates anywhere, no
negative money, no duplicate valuation snapshots, perfect game_id integrity, consistent player
names. The real hazards are structural, not dirty cells: incomplete club dimension, sparse
valuation snapshots around transfers, censored transfer fees, future-dated transfer rows, and
scrape-state columns that leak the future (§10).
