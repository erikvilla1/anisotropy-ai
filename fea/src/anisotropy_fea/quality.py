"""Mesh quality, per element, for the studio's setup check (ADR-0051).

`Mesh2D` refuses a mesh that is not a valid finite element mesh (clockwise, degenerate or repeated nodes). This module measures
how good a valid mesh is, by the four shape measures a mesh checker usually reports for a quadrilateral: the aspect ratio
(longest edge over shortest), the smallest and the largest interior angle, and the Jacobian ratio (the smallest over the largest
of the element's corner Jacobians: 1 for a parallelogram, 0 at a corner where the element folds). The thresholds are our own
choice for a warning and carry no evidence yet; a mesh over them still solves. A warning never refuses a run: it is for the
engineer to read.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

THRESHOLDS = {"aspect_ratio": 10.0, "min_angle_deg": 10.0, "max_angle_deg": 160.0, "jacobian_ratio": 0.1}  # our choice; no evidence yet
WORSE = {"aspect_ratio": "above", "min_angle_deg": "below", "max_angle_deg": "above", "jacobian_ratio": "below"}  # which side of a threshold warns
WORDS = {"aspect_ratio": "aspect ratio", "min_angle_deg": "smallest angle", "max_angle_deg": "largest angle", "jacobian_ratio": "Jacobian ratio"}
CORNERS = np.array([[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0]])  # natural coordinates of the four corners


@dataclass(frozen=True)
class QualityField:
    """One value per element, in element order."""

    aspect_ratio: np.ndarray  # (ne,) longest edge over shortest edge, at least 1
    min_angle_deg: np.ndarray  # (ne,) the smallest interior angle
    max_angle_deg: np.ndarray  # (ne,) the largest interior angle
    jacobian_ratio: np.ndarray  # (ne,) smallest over largest corner Jacobian; 1 for a parallelogram, 0 or negative where the element folds

    @property
    def element_count(self) -> int:
        return int(self.aspect_ratio.size)


def corner_jacobians(p: np.ndarray) -> np.ndarray:
    """The Jacobian determinant of the bilinear map at the four corners of one element whose corners are the rows of `p` (4, 2)."""
    out = np.empty(4)
    for c, (xi, eta) in enumerate(CORNERS):
        d_xi = 0.25 * np.array([-(1 - eta), (1 - eta), (1 + eta), -(1 + eta)])
        d_eta = 0.25 * np.array([-(1 - xi), -(1 + xi), (1 + xi), (1 - xi)])
        jacobian = np.array([d_xi @ p, d_eta @ p])
        out[c] = np.linalg.det(jacobian)
    return out


def element_quality(xy: np.ndarray, corners: np.ndarray) -> QualityField:
    """The four measures for every element of a corner-node mesh: `xy` (n, 2) and `corners` (ne, 4), counterclockwise."""
    xy, corners = np.asarray(xy, dtype=float), np.asarray(corners, dtype=int)
    if corners.ndim != 2 or corners.shape[1] != 4:
        raise ValueError("corners must be (ne, 4)")
    ne = corners.shape[0]
    aspect, smallest, largest, ratio = np.empty(ne), np.empty(ne), np.empty(ne), np.empty(ne)
    for e in range(ne):
        p = xy[corners[e]]
        edges = np.roll(p, -1, axis=0) - p
        lengths = np.linalg.norm(edges, axis=1)
        if lengths.min() <= 0.0:
            raise ValueError(f"element {e + 1}: an edge has zero length")
        aspect[e] = lengths.max() / lengths.min()
        angles = np.empty(4)
        for k in range(4):
            before, after = -edges[k - 1], edges[k]
            cosine = float(before @ after) / (np.linalg.norm(before) * np.linalg.norm(after))
            angles[k] = np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))
        smallest[e], largest[e] = angles.min(), angles.max()
        jac = corner_jacobians(p)
        ratio[e] = jac.min() / jac.max() if jac.max() > 0 else 0.0
    return QualityField(aspect_ratio=aspect, min_angle_deg=smallest, max_angle_deg=largest, jacobian_ratio=ratio)


def quality_summary(field: QualityField, thresholds: dict[str, float] | None = None) -> dict:
    """Per measure: the worst value, the element that has it (index from 0), the threshold and how many elements lie past it; and
    whether the whole mesh is within every threshold."""
    thresholds = {**THRESHOLDS, **(thresholds or {})}
    summary: dict = {"elements": field.element_count, "measures": {}}
    acceptable = True
    for name, side in WORSE.items():
        values = getattr(field, name)
        if side == "above":
            worst, over = int(np.argmax(values)), int(np.sum(values > thresholds[name]))
        else:
            worst, over = int(np.argmin(values)), int(np.sum(values < thresholds[name]))
        acceptable = acceptable and over == 0
        summary["measures"][name] = {"word": WORDS[name], "worst": float(values[worst]), "element": worst, "threshold": thresholds[name],
                                     "warns": side, "over": over}
    summary["acceptable"] = acceptable
    return summary


def quality_words(summary: dict) -> str:
    """One sentence per measure: the worst value and how many elements pass the threshold."""
    parts = []
    for name, m in summary["measures"].items():
        unit = "°" if "angle" in name else ""
        text = f"{m['word']} {m['worst']:.3g}{unit} at worst (warns {m['warns']} {m['threshold']:g}{unit})"
        if m["over"]:
            text += f": {m['over']} element{'s' if m['over'] != 1 else ''} past it"
        parts.append(text)
    return "; ".join(parts)
