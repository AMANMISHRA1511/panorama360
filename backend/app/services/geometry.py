"""Camera geometry and overlap matching for Panorama360 (compatible v2).

Conventions:
  x right, y down, z forward; R maps world directions to camera directions.
  Equirectangular longitude [-pi, pi], latitude [pi/2, -pi/2].
  rotation_xyz = Rz @ Ry @ Rx (angles in radians).

This estimates rotations from overlapping photos. It does not reconstruct
unseen camera viewpoints and requires static visual detail and real overlap.
"""

import math

import cv2
import numpy as np


def intrinsic_matrix(width: int, height: int, fov_degrees: float = 90.0) -> np.ndarray:
    if width < 2 or height < 2:
        raise ValueError("Image width and height must be at least 2 pixels")
    if not 20 <= fov_degrees <= 160:
        raise ValueError("Field of view must be between 20 and 160 degrees")
    focal = width / (2.0 * math.tan(math.radians(fov_degrees) / 2.0))
    return np.array(
        [[focal, 0, (width - 1) / 2],
         [0, focal, (height - 1) / 2],
         [0, 0, 1]], dtype=np.float64
    )


def rotation_xyz(rx: float = 0, ry: float = 0, rz: float = 0) -> np.ndarray:
    """Return rotation in the required exact order Rz @ Ry @ Rx."""
    sx, cx = math.sin(rx), math.cos(rx)
    sy, cy = math.sin(ry), math.cos(ry)
    sz, cz = math.sin(rz), math.cos(rz)
    rxm = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    rym = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rzm = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rzm @ rym @ rxm


def normalize_rotation(approximate: np.ndarray) -> np.ndarray:
    approximate = np.asarray(approximate, dtype=np.float64)
    if approximate.shape != (3, 3) or not np.isfinite(approximate).all():
        raise ValueError("Rotation must be a finite 3x3 matrix")
    u, _, vt = np.linalg.svd(approximate)
    correction = np.diag([1.0, 1.0, np.linalg.det(u @ vt)])
    return u @ correction @ vt


def rotation_from_homography(
    homography: np.ndarray, k_source: np.ndarray, k_destination: np.ndarray
) -> np.ndarray:
    """For H(current -> previous), recover world-to-current camera rotation.

    H ~ K_previous @ (R_previous @ R_current.T) @ inv(K_current).
    When previous orientation is identity, R_current is the inverse of the
    normalized rotational component of H.
    """
    h = np.asarray(homography, dtype=np.float64)
    if h.shape != (3, 3) or not np.isfinite(h).all():
        raise ValueError("Homography must be a finite 3x3 matrix")
    candidate = np.linalg.solve(k_destination, h @ k_source)
    if np.linalg.det(candidate) < 0:
        candidate = -candidate
    return normalize_rotation(candidate).T


def equirectangular_directions(width: int, height: int) -> np.ndarray:
    if width < 2 or height < 2:
        raise ValueError("Panorama dimensions must be at least 2 pixels")
    xs = (np.arange(width, dtype=np.float32) + 0.5) / width
    ys = (np.arange(height, dtype=np.float32) + 0.5) / height
    lon = (xs * 2 - 1) * np.pi
    lat = (0.5 - ys) * np.pi
    lon, lat = np.meshgrid(lon, lat)
    return np.stack(
        [np.cos(lat) * np.sin(lon), -np.sin(lat), np.cos(lat) * np.cos(lon)],
        axis=-1,
    )


def spherical_warp(
    image: np.ndarray, rotation: np.ndarray,
    output_size=(2048, 1024), fov=90
):
    """Output pixel -> unit ray -> R -> K -> cv2.remap with validity mask.

    Uses row chunks to avoid allocating large 3D direction arrays for every
    output pixel at once, especially on CPU-only Windows machines.
    """
    if not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Input must be an HxWx3 BGR image")
    height, width = image.shape[:2]
    out_w, out_h = map(int, output_size)
    if out_w < 2 or out_h < 2:
        raise ValueError("Output panorama dimensions must be at least 2")
    rotation = normalize_rotation(rotation).astype(np.float32)
    k = intrinsic_matrix(width, height, fov)
    fx, fy, cx, cy = k[0, 0], k[1, 1], k[0, 2], k[1, 2]
    lon = ((np.arange(out_w, dtype=np.float32) + 0.5) / out_w * 2 - 1) * np.pi
    sin_lon, cos_lon = np.sin(lon)[None, :], np.cos(lon)[None, :]
    warped = np.zeros((out_h, out_w, 3), dtype=image.dtype)
    mask = np.zeros((out_h, out_w), dtype=np.uint8)
    for start in range(0, out_h, 128):
        stop = min(start + 128, out_h)
        lat = (0.5 - (np.arange(start, stop, dtype=np.float32) + 0.5) / out_h) * np.pi
        sin_lat, cos_lat = np.sin(lat)[:, None], np.cos(lat)[:, None]
        world = np.stack(
            [cos_lat * sin_lon,
             np.broadcast_to(-sin_lat, (stop - start, out_w)),
             cos_lat * cos_lon], axis=-1,
        )
        camera = world @ rotation.T
        z = camera[..., 2]
        front = z > 1e-6
        safe_z = np.where(front, z, 1.0)
        x_map = (fx * camera[..., 0] / safe_z + cx).astype(np.float32)
        y_map = (fy * camera[..., 1] / safe_z + cy).astype(np.float32)
        valid = (front & (x_map >= 0) & (x_map < width - 1)
                 & (y_map >= 0) & (y_map < height - 1))
        x_map[~valid] = -1
        y_map[~valid] = -1
        warped[start:stop] = cv2.remap(
            image, x_map, y_map, cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
        )
        mask[start:stop] = valid.astype(np.uint8) * 255
    return warped, mask


def _feature_attempt(prev_gray, curr_gray, detector, norm, ratio):
    """Return a valid current-to-previous homography, or diagnostics.

    Reject low-consensus and spatially clustered matches instead of creating
    a falsely aligned panorama from a few unrelated points.
    """
    kp_prev, desc_prev = detector.detectAndCompute(prev_gray, None)
    kp_curr, desc_curr = detector.detectAndCompute(curr_gray, None)
    if (desc_prev is None or desc_curr is None or
            len(desc_prev) < 2 or len(desc_curr) < 2):
        return None, 0, 0

    pairs = cv2.BFMatcher(norm).knnMatch(desc_curr, desc_prev, k=2)
    good = [m for pair in pairs if len(pair) == 2
            for m, n in [pair] if m.distance < ratio * n.distance]
    if len(good) < 12:
        return None, len(good), 0

    src = np.float32([kp_curr[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kp_prev[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    h, inlier_mask = cv2.findHomography(
        src, dst, cv2.RANSAC, 4.0,
        maxIters=5000, confidence=0.997,
    )
    count = int(inlier_mask.sum()) if inlier_mask is not None else 0
    if (h is None or count < 10 or count / len(good) < 0.30 or
            not np.isfinite(h).all() or abs(np.linalg.det(h)) < 1e-12):
        return None, len(good), count

    # A handful of matches in a single corner can yield an unstable H.
    selected = np.flatnonzero(inlier_mask.ravel())
    matched = dst[selected, 0, :]
    width, height = prev_gray.shape[1], prev_gray.shape[0]
    if (np.ptp(matched[:, 0]) < 0.035 * width or
            np.ptp(matched[:, 1]) < 0.035 * height):
        return None, len(good), count
    return h, len(good), count


def feature_match_rotation(previous: np.ndarray, current: np.ndarray, fov=90) -> np.ndarray:
    """Estimate relative camera rotation from overlapping static photos.

    SIFT on normal and contrast-enhanced images, with ORB fallback. Try
    modestly downsampled photos first to reduce matching CPU and memory costs.
    Invalid matches raise a specific error rather than a made-up rotation.

    IMPORTANT: The unordered-photo graph in stitch.py uses its own detector;
    this routine cannot repair an overlap graph with disconnected images.
    """
    for img in (previous, current):
        if (not isinstance(img, np.ndarray) or img.ndim != 3 or
                img.shape[2] != 3 or img.dtype != np.uint8):
            raise ValueError("Images must be uint8 HxWx3 BGR arrays")
        if min(img.shape[:2]) < 32:
            raise ValueError("Images are too small for reliable feature matching")
    intrinsic_matrix(previous.shape[1], previous.shape[0], fov)
    intrinsic_matrix(current.shape[1], current.shape[0], fov)

    # Keep the camera intrinsic matrices consistent with the image resolution
    # used in each matching attempt (important when photos have different sizes).
    max_side = 1400
    small = []
    for img in (previous, current):
        height, width = img.shape[:2]
        scale = min(1.0, max_side / max(height, width))
        if scale < 1.0:
            size = (max(32, round(width * scale)), max(32, round(height * scale)))
            img = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
        small.append(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    gray_prev, gray_curr = small
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    light_prev, light_curr = clahe.apply(gray_prev), clahe.apply(gray_curr)
    attempts = []
    if hasattr(cv2, "SIFT_create"):
        attempts.extend([
            (gray_prev, gray_curr, "sift"),
            (light_prev, light_curr, "sift"),
        ])
    attempts.extend([
        (gray_prev, gray_curr, "orb"),
        (light_prev, light_curr, "orb"),
    ])

    best_matches = best_inliers = 0
    for prev_gray, curr_gray, method in attempts:
        if method == "sift":
            detector = cv2.SIFT_create(nfeatures=4200, contrastThreshold=0.012)
            norm, ratio = cv2.NORM_L2, 0.78
        else:
            detector = cv2.ORB_create(nfeatures=5500, fastThreshold=8)
            norm, ratio = cv2.NORM_HAMMING, 0.80
        h, matches, inliers = _feature_attempt(
            prev_gray, curr_gray, detector, norm, ratio
        )
        best_matches = max(best_matches, matches)
        best_inliers = max(best_inliers, inliers)
        if h is None:
            continue
        k_curr = intrinsic_matrix(curr_gray.shape[1], curr_gray.shape[0], fov)
        k_prev = intrinsic_matrix(prev_gray.shape[1], prev_gray.shape[0], fov)
        try:
            rotation = rotation_from_homography(h, k_curr, k_prev)
        except (ValueError, np.linalg.LinAlgError):
            continue
        if np.isfinite(rotation).all():
            return rotation

    if best_matches < 12:
        raise ValueError(
            "Not enough reliable visual features or overlap "
            f"({best_matches} descriptor matches; need at least 12). "
            "Capture overlapping, well-lit photos from one fixed position."
        )
    raise ValueError(
        "Could not estimate a reliable rotational homography "
        f"({best_inliers} RANSAC inliers). Check blur, repeated textures, "
        "moving objects, camera translation, and photo overlap."
    )
