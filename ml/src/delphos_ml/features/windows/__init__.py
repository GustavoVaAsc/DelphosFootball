"""Trailing-window feature indexes for point-in-time queries.

Input: the raw ingest frames a window concept is built from (see the concrete index class).
Output: `TrailingWindowIndex`, the public window-index surface of this concept.
Responsibility: re-export the concept's public surface; the implementation lives in
`trailing_window_index` and this facade only imports from it.
"""

from delphos_ml.features.windows.trailing_window_index import TrailingWindowIndex

__all__ = ["TrailingWindowIndex"]
