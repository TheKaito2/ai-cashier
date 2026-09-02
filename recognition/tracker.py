"""Count each item once.

v3 took one snapshot per SCAN press, so an item could be counted twice and a
second camera could not be combined with the first.  Tracking gives every object
a stable id, which is both how repeated frames get collapsed into one cart line
and how the two cameras will be fused later - by id, not by hoping.

A centroid tracker is enough: items are placed on a mat and stay put, so there
is no occlusion or fast motion to justify a heavier tracker.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np


def _centre(box: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = box
    return np.array([(x1 + x2) / 2.0, (y1 + y2) / 2.0])


@dataclass
class Track:
    track_id: int
    box: tuple[int, int, int, int]
    votes: Counter = field(default_factory=Counter)
    scores: dict[str, float] = field(default_factory=dict)
    misses: int = 0
    hits: int = 1

    def observe(self, sku_id: str | None, score: float) -> None:
        """Record one frame's opinion. `None` means 'nothing matched'."""
        key = sku_id if sku_id is not None else "__unknown__"
        self.votes[key] += 1
        self.scores[key] = max(self.scores.get(key, -2.0), score)

    @property
    def decision(self) -> tuple[str | None, float, float]:
        """(sku_id, best score, agreement) from every frame seen so far.

        Voting over frames beats trusting a single frame - a glare or a hand in
        the way costs one vote instead of the whole decision.
        """
        if not self.votes:
            return None, 0.0, 0.0
        key, count = self.votes.most_common(1)[0]
        agreement = count / sum(self.votes.values())
        sku = None if key == "__unknown__" else key
        return sku, self.scores.get(key, 0.0), agreement


class CentroidTracker:
    def __init__(self, max_distance_px: float = 80.0, max_misses: int = 5,
                 min_hits: int = 2):
        self.max_distance_px = max_distance_px
        self.max_misses = max_misses
        self.min_hits = min_hits
        self.tracks: dict[int, Track] = {}
        self._next_id = 1

    def update(self, boxes: list[tuple[int, int, int, int]]) -> list[Track]:
        """Associate this frame's boxes with existing tracks. Returns live tracks."""
        unmatched = set(self.tracks)

        for box in boxes:
            c = _centre(box)
            best_id, best_d = None, self.max_distance_px
            for tid in unmatched:
                d = float(np.linalg.norm(_centre(self.tracks[tid].box) - c))
                if d < best_d:
                    best_id, best_d = tid, d

            if best_id is None:
                t = Track(track_id=self._next_id, box=box)
                self.tracks[self._next_id] = t
                self._next_id += 1
            else:
                t = self.tracks[best_id]
                t.box = box
                t.misses = 0
                t.hits += 1
                unmatched.discard(best_id)

        for tid in unmatched:
            self.tracks[tid].misses += 1

        # a track that has been gone for a while is a different object next time
        for tid in [t for t, tr in self.tracks.items() if tr.misses > self.max_misses]:
            del self.tracks[tid]

        return list(self.tracks.values())

    @property
    def confirmed(self) -> list[Track]:
        """Tracks seen enough times to be worth charging for."""
        return [t for t in self.tracks.values() if t.hits >= self.min_hits and t.misses == 0]

    def reset(self) -> None:
        self.tracks.clear()
