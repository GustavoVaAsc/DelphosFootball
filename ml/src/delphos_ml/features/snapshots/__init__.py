"""End-of-season player-season snapshots and paid-transfer event rows for the `transform` stage.

Input: the typed `player_valuations`, `players`, `transfers` and `clubs` frames from
`data/clean/`, the point-in-time club league-position lookup the stage builds from `club_games`
and `games`, plus the trailing-window indexes over the appearance frames.
Output: one DataFrame per population — the Option A player-season rows and the paid-transfer
event rows — carrying the raw window counts and deterministic derived columns of the
`ml/data/transform/` schema.
Responsibility: own the population rules (July-to-June seasons 2017 to 2025, 14 covered
leagues, outfield players only, minutes floor) and re-export this concept's public surface.
No learned statistic is computed here; the Empirical Bayes priors, imputers and scalers belong
to the fitted preprocessor that `train` fits on the training split.
"""

from delphos_ml.features.snapshots.build_player_seasons import build_player_seasons
from delphos_ml.features.snapshots.build_transfer_events import build_transfer_events
from delphos_ml.features.snapshots.season import assign_split, season_of

__all__ = ["assign_split", "build_player_seasons", "build_transfer_events", "season_of"]
