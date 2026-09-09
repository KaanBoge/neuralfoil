"""Optional numerical Airfoil normalization convention; never patches AeroSandbox.

For unique farthest-TE vertices this delegates exactly to AeroSandbox. For ties
within 16 float64 eps relative to maximum distance, use their centroid as LE.
This changes the geometry input convention and implies no accuracy improvement.
"""
import numpy as np

TIE_RTOL = 16 * np.finfo(np.float64).eps


def normalize_tie_safe(airfoil, return_dict=False):
    coordinates = np.asarray(airfoil.coordinates, dtype=float)
    if coordinates.ndim != 2 or coordinates.shape[1] != 2 or len(coordinates) < 3:
        raise ValueError("Expected at least three finite two-dimensional vertices")
    if not np.isfinite(coordinates).all():
        raise ValueError("Coordinates must be finite")
    te = (coordinates[0] + coordinates[-1]) / 2
    distances = np.sqrt(np.sum((coordinates-te)**2, axis=1))
    maximum = float(distances.max())
    if maximum <= 0:
        raise ValueError("Degenerate zero-chord geometry")
    tied = np.flatnonzero(maximum-distances <= TIE_RTOL*maximum)
    if len(tied) == 1:
        result = airfoil.normalize(return_dict=True)
    else:
        le = coordinates[tied].mean(axis=0)
        chord = float(np.linalg.norm(te-le))
        if chord <= 0:
            raise ValueError("Tie centroid has zero chord")
        moved = airfoil.translate(translate_x=-le[0], translate_y=-le[1])
        scale = 1/chord
        scaled = moved.scale(scale_x=scale, scale_y=scale)
        normalized_te = (scaled.coordinates[0] + scaled.coordinates[-1])/2
        rotation = -np.arctan2(normalized_te[1], normalized_te[0])
        result = {"airfoil": scaled.rotate(angle=rotation),
                  "x_translation": float(-le[0]), "y_translation": float(-le[1]),
                  "scale_factor": scale, "rotation_angle": float(np.degrees(rotation))}
    result = {**result, "le_tie_indices": tied.tolist(), "le_tie_count": len(tied),
              "tie_relative_tolerance": TIE_RTOL, "tie_safe_applied": len(tied) > 1}
    return result if return_dict else result["airfoil"]


def to_kulfan_tie_safe(airfoil, return_dict=False, **kulfan_options):
    """Normalize once and explicitly prevent the fitter from normalizing again.

    With return_dict=True, return normalization metadata plus `kulfan_airfoil`.
    Callers converting dimensional/inlet conditions must apply the returned
    rotation and chord scale consistently with their chosen inference interface.
    """
    if "normalize_coordinates" in kulfan_options:
        raise ValueError("normalize_coordinates is controlled by this wrapper")
    result = normalize_tie_safe(airfoil, return_dict=True)
    fitted = result["airfoil"].to_kulfan_airfoil(
        normalize_coordinates=False, **kulfan_options)
    return {**result, "kulfan_airfoil": fitted} if return_dict else fitted
