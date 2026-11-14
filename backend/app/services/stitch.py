

import cv2
import numpy as np

from app.services.geometry import (
    feature_match_rotation,
    normalize_rotation,
    spherical_warp,
)

DEFAULT_SIZE = (2048, 1024)


def _emit_progress(callback, stage, done, total):
    """Report real work; never report 100% while stitching is still running."""
    if callback is not None:
        callback(stage, int(done), max(1, int(total)))


def read_image(path: str) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Unable to decode image; use a valid JPG, PNG or WEBP")
    h, w = image.shape[:2]
    if min(h, w) < 64:
        raise ValueError("Image must be at least 64 x 64 pixels")
    if w > 1800:
        image = cv2.resize(image, (1800, max(1, round(h * 1800 / w))),
                           interpolation=cv2.INTER_AREA)
    return image


def is_equirectangular(image: np.ndarray) -> bool:
    """Aspect-ratio heuristic, not a guarantee that the photo is 360 degrees."""
    h, w = image.shape[:2]
    return h > 0 and abs(w / h - 2.0) < 0.045


def wrap_seam(image: np.ndarray, strip: int = 18) -> np.ndarray:
    """Feather the periodic left/right edges and make endpoint pixels equal."""
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Expected HxWx3 image")
    result = image.copy()
    width = image.shape[1]
    if width < 2:
        return result
    strip = max(1, min(int(strip), max(1, width // 8)))
    for j in range(strip):
        left = image[:, j].astype(np.float32)
        right = image[:, width - 1 - j].astype(np.float32)
        # Strongly feather the exact seam, taper into untouched image interiors.
        weight = 0.5 * (1.0 - j / max(1, strip)) ** 2
        result[:, j] = np.clip((1 - weight) * left + weight * right, 0, 255)
        result[:, width - 1 - j] = np.clip((1 - weight) * right + weight * left, 0, 255)
    endpoint = np.rint(
        (result[:, 0].astype(np.float32) + result[:, -1].astype(np.float32)) / 2
    ).astype(image.dtype)
    result[:, 0] = endpoint
    result[:, -1] = endpoint
    return result


def _pyramid(image, levels):
    gauss = [image]
    for _ in range(levels - 1):
        gauss.append(cv2.pyrDown(gauss[-1]))
    return gauss


def multiband_blend(warped_images, masks, levels=5, progress_callback=None):
    """Multi-band masked blend using streaming pyramid accumulation.

    Unlike storing every image's pyramid, this only keeps the running weighted
    sum and denominator per level; memory grows slowly with input count.
    """
    if not warped_images or len(warped_images) != len(masks):
        raise ValueError("Provide corresponding nonempty image and mask lists")
    h, w = warped_images[0].shape[:2]
    for image, mask in zip(warped_images, masks):
        if image.shape != (h, w, 3) or mask.shape != (h, w):
            raise ValueError("All warped images and masks must have matching sizes")
    if len(warped_images) == 1:
        return warped_images[0].copy(), masks[0].copy()

    levels = max(1, min(int(levels), max(1, int(np.log2(min(h, w))) - 2)))
    accum = denominator = None
    coverage = np.zeros((h, w), dtype=np.uint8)

    _emit_progress(progress_callback, "Blending photographs", 0, len(warped_images) + 1)
    for image_index, (image, mask) in enumerate(zip(warped_images, masks), 1):
        coverage = np.maximum(coverage, mask)
        img_gauss = _pyramid(image.astype(np.float32), levels)
        mask_gauss = _pyramid((mask > 0).astype(np.float32), levels)
        if accum is None:
            accum = [np.zeros_like(level_img) for level_img in img_gauss]
            denominator = [np.zeros(level_mask.shape, dtype=np.float32)
                           for level_mask in mask_gauss]
        for i in range(levels):
            if i == levels - 1:
                lap = img_gauss[i]
            else:
                lap = img_gauss[i] - cv2.pyrUp(
                    img_gauss[i + 1],
                    dstsize=(img_gauss[i].shape[1], img_gauss[i].shape[0]),
                )
            weight = mask_gauss[i]
            accum[i] += lap * weight[..., None]
            denominator[i] += weight
        _emit_progress(progress_callback, "Blending photographs", image_index, len(warped_images) + 1)

    result_levels = [
        accum[i] / np.maximum(denominator[i][..., None], 1e-6)
        for i in range(levels)
    ]
    result = result_levels[-1]
    for i in range(levels - 2, -1, -1):
        result = cv2.pyrUp(
            result,
            dstsize=(result_levels[i].shape[1], result_levels[i].shape[0]),
        ) + result_levels[i]
    result[coverage == 0] = 0
    _emit_progress(progress_callback, "Blending photographs", len(warped_images) + 1, len(warped_images) + 1)
    return np.clip(result, 0, 255).astype(np.uint8), coverage


def compensate_exposure(warped, mask, reference, refmask):
    """Channel-wise exposure gain estimated from shared valid pixels only."""
    overlap = (mask > 0) & (refmask > 0)
    if np.count_nonzero(overlap) < 250:
        return warped
    mean_new = warped[overlap].mean(axis=0)
    mean_ref = reference[overlap].mean(axis=0)
    gain = np.clip((mean_ref + 1.0) / (mean_new + 1.0), 0.65, 1.50)
    return np.clip(warped.astype(np.float32) * gain, 0, 255).astype(np.uint8)


def fill_missing_deterministic(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Periodic interpolation in each row; known pixels remain unchanged.

    Entirely missing rows are filled from the nearest *already interpolated*
    row. The result is a visual placeholder, not a reconstructed viewpoint.
    """
    if mask.shape != image.shape[:2]:
        raise ValueError("Mask must have the same height and width as the image")
    missing = mask == 0
    if not missing.any():
        return image.copy()
    output = image.copy()
    height, width = missing.shape
    x_values = np.arange(width)
    valid_rows = np.flatnonzero((~missing).any(axis=1))
    if valid_rows.size == 0:
        raise ValueError("No image pixels mapped to the panorama")
    for row in valid_rows:
        absent = missing[row]
        if not absent.any():
            continue
        known = x_values[~absent]
        periodic_x = np.concatenate([known - width, known, known + width])
        for channel in range(3):
            values = image[row, known, channel].astype(np.float32)
            periodic_y = np.tile(values, 3)
            output[row, absent, channel] = np.interp(
                x_values[absent], periodic_x, periodic_y
            ).astype(np.uint8)
    missing_rows = np.flatnonzero(missing.all(axis=1))
    for row in missing_rows:
        closest = valid_rows[np.argmin(np.abs(valid_rows - row))]
        output[row] = output[closest]
    return output



def show_missing_as_blank(image, coverage, fill_bgr=(50, 39, 27)):
    """Mark unphotographed directions without hallucination or horizontal streaks.

    Valid pixels are never changed. A binary coverage mask can be scaled when
    enhancement has changed the output dimensions.
    """
    if not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Expected HxWx3 BGR image")
    if not isinstance(coverage, np.ndarray) or coverage.ndim != 2:
        raise ValueError("Expected HxW coverage mask")
    valid = cv2.resize(
        (coverage > 0).astype(np.uint8),
        (image.shape[1], image.shape[0]),
        interpolation=cv2.INTER_NEAREST,
    ) > 0
    result = image.copy()
    result[~valid] = fill_bgr
    return result


def to_panorama(image, output_size=DEFAULT_SIZE, fov=90):
    if is_equirectangular(image):
        pano = cv2.resize(image, output_size, interpolation=cv2.INTER_AREA)
        return pano, np.full((output_size[1], output_size[0]), 255, np.uint8)
    return spherical_warp(image, np.eye(3), output_size, fov)


def stitch_images(images, output_size=DEFAULT_SIZE, fov=90, progress_callback=None):
    """Align consecutive overlapping photos and blend onto a partial/full sphere."""
    if not 2 <= len(images) <= 32:
        raise ValueError("Upload between 2 and 32 overlapping photos for stitching")
    rotations = [np.eye(3)]
    _emit_progress(progress_callback, "Matching consecutive photos", 0, len(images) - 1)
    for i in range(1, len(images)):
        try:
            relative = feature_match_rotation(images[i - 1], images[i], fov)
        except ValueError as exc:
            raise ValueError(
                f"Cannot stitch image {i} with image {i + 1}: {exc} "
                "Please upload consecutive photographs of a static scene "
                "with substantial overlap."
            ) from exc
        rotations.append(normalize_rotation(relative @ rotations[-1]))
        _emit_progress(progress_callback, "Matching consecutive photos", i, len(images) - 1)

    warped_images, masks = [], []
    _emit_progress(progress_callback, "Projecting photos", 0, len(images))
    for index, (image, rotation) in enumerate(zip(images, rotations), 1):
        warped, mask = spherical_warp(image, rotation, output_size, fov)
        if warped_images:
            warped = compensate_exposure(warped, mask, warped_images[-1], masks[-1])
        warped_images.append(warped)
        masks.append(mask)
        _emit_progress(progress_callback, "Projecting photos", index, len(images))
    return multiband_blend(warped_images, masks, progress_callback=progress_callback)

# --- Confidence-based matching for uploads that are not in camera order ---

def _match_graph(images, fov, progress_callback=None):
    """Precompute SIFT features once and find high-confidence pairwise overlaps.

    A graph edge is not a guarantee of perfect registration. Conservative limits
    reject weak RANSAC consensus, rather than inventing a 360-degree scene.
    """
    from app.services.geometry import intrinsic_matrix, rotation_from_homography

    detector = (cv2.SIFT_create(nfeatures=2300, contrastThreshold=0.018)
                if hasattr(cv2, 'SIFT_create') else cv2.ORB_create(nfeatures=3000))
    norm = cv2.NORM_L2 if hasattr(cv2, 'SIFT_create') else cv2.NORM_HAMMING
    ratio = .76 if norm == cv2.NORM_L2 else .78
    features = []
    scaled_sizes = []
    _emit_progress(progress_callback, "Detecting image features", 0, len(images))
    for image_index, image in enumerate(images, 1):
        h, w = image.shape[:2]
        s = min(1., 950. / max(w, h))
        scaled = cv2.resize(image, (max(2,round(w*s)),max(2,round(h*s))),
                            interpolation=cv2.INTER_AREA) if s < 1 else image
        g = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
        g = cv2.createCLAHE(2.1,(8,8)).apply(g)
        kp, desc = detector.detectAndCompute(g, None)
        features.append((kp, desc))
        scaled_sizes.append((scaled.shape[1],scaled.shape[0]))
        _emit_progress(progress_callback, "Detecting image features", image_index, len(images))
    matcher = cv2.BFMatcher(norm)
    graph = {i: [] for i in range(len(images))}
    edges = []
    pair_total = len(images) * (len(images) - 1) // 2
    pair_number = 0
    _emit_progress(progress_callback, "Checking photo overlaps", 0, pair_total)
    for i in range(len(images)):
        kp_i, desc_i = features[i]
        for j in range(i+1,len(images)):
            pair_number += 1
            _emit_progress(progress_callback, "Checking photo overlaps", pair_number - 1, pair_total)
            if desc_i is None or len(desc_i) < 2:
                continue
            kp_j, desc_j = features[j]
            if desc_j is None or len(desc_j)<2:
                continue
            pairs = matcher.knnMatch(desc_j, desc_i, k=2)
            good = [m for pair in pairs if len(pair)==2
                    for m,n in [pair] if m.distance < ratio*n.distance]
            if len(good) < 20:
                continue
            src=np.float32([kp_j[m.queryIdx].pt for m in good]).reshape(-1,1,2)
            dst=np.float32([kp_i[m.trainIdx].pt for m in good]).reshape(-1,1,2)
            H, inlier_mask = cv2.findHomography(src,dst,cv2.RANSAC,4.0,
                                               maxIters=5000,confidence=.997)
            if H is None or inlier_mask is None or not np.isfinite(H).all():
                continue
            inliers=int(inlier_mask.sum())
            fraction=inliers/len(good)
            if inliers < 20 or fraction < .30:
                continue
            # At least a modest, two-dimensional feature footprint.
            selected = np.flatnonzero(inlier_mask.ravel())
            xy = dst[selected,0,:]
            wi,hi = scaled_sizes[i]
            if np.ptp(xy[:,0]) < .07*wi or np.ptp(xy[:,1]) < .07*hi:
                continue
            wj,hj = scaled_sizes[j]
            try:
                rel=rotation_from_homography(H, intrinsic_matrix(wj,hj,fov),
                                             intrinsic_matrix(wi,hi,fov))
            except (ValueError,np.linalg.LinAlgError):
                continue
            angle=np.degrees(np.arccos(np.clip((np.trace(rel)-1)/2,-1,1)))
            if angle > 135:
                continue
            score = inliers * fraction
            graph[i].append((j,rel,score))
            graph[j].append((i,rel.T,score))
            edges.append((i,j,inliers,round(fraction,2)))
    _emit_progress(progress_callback, "Checking photo overlaps", pair_total, pair_total)
    return graph, edges


def _connected_groups(graph):
    remaining=set(graph)
    groups=[]
    while remaining:
        root=min(remaining)
        visited={root}
        stack=[root]
        remaining.remove(root)
        while stack:
            cur=stack.pop()
            for j,_,_ in graph[cur]:
                if j in remaining:
                    remaining.remove(j)
                    visited.add(j)
                    stack.append(j)
        groups.append(sorted(visited))
    return sorted(groups,key=lambda g:(-len(g),g[0]))


def _auto_rotations(images, fov, progress_callback=None):
    """Build a maximum-confidence spanning tree to align unordered images.

    Refuse to fabricate rotations if there is no real overlap path linking every
    image; for incomplete sets, returns a specific, actionable error.
    """
    graph, edges = _match_graph(images,fov,progress_callback=progress_callback)
    groups=_connected_groups(graph)
    if len(groups)>1:
        readable='; '.join('['+', '.join(str(i+1) for i in g)+']' for g in groups)
        strongest=sorted(edges,key=lambda e:(-e[2]*e[3]))[:4]
        pairs=', '.join(f'{a+1}-{b+1} ({n} inliers)' for a,b,n,r in strongest) or 'none'
        raise ValueError(
            'These photos cannot form one reliable panorama: no overlap path connects '
            'all uploads. Matched groups (upload positions): '+readable+'. '
            'Strongest matched pairs: '+pairs+'. '
            'Capture a horizontal rotation sequence from one fixed position, '
            'with 60-70% overlap between EVERY neighboring photo. '
            'Take ceiling and floor photos separately after completing the horizontal ring.'
        )
    rotations=[None]*len(images)
    rotations[0]=np.eye(3)
    visited={0}
    while len(visited)<len(images):
        possible=[(score,i,j,rel) for i in visited
                  for j,rel,score in graph[i] if j not in visited]
        if not possible:
            raise ValueError('No reliable connection for the remaining photos')
        score,i,j,rel=max(possible,key=lambda e:e[0])
        rotations[j]=normalize_rotation(rel@rotations[i])
        visited.add(j)
    return rotations


# Use the existing fast consecutive matcher first, followed by overlap graph
# recovery only when that fast path fails.
_consecutive_stitch_images = stitch_images

def stitch_images(images, output_size=DEFAULT_SIZE, fov=90, progress_callback=None):
    """Create a partial/full sphere from overlapping photos in arbitrary order.

    For good consecutive captures this uses the original path. If upload order is
    mixed, match pairs globally and align via a confidence-weighted graph. A
    disconnected set fails explicitly rather than filling unseen directions.
    """
    if not 2 <= len(images) <= 32:
        raise ValueError('Upload between 2 and 32 overlapping photos for stitching')
    try:
        return _consecutive_stitch_images(images, output_size, fov, progress_callback=progress_callback)
    except ValueError as first_failure:
        # Two photos cannot be reordered into a different pairing.
        if len(images)==2:
            raise
        try:
            rotations=_auto_rotations(images,fov,progress_callback=progress_callback)
        except ValueError as diagnostic:
            raise ValueError(str(diagnostic)) from first_failure
        warped_images, masks = [], []
        _emit_progress(progress_callback, "Projecting photos", 0, len(images))
        for index, (image,rotation) in enumerate(zip(images,rotations), 1):
            warped,mask=spherical_warp(image,rotation,output_size,fov)
            if warped_images:
                warped=compensate_exposure(warped,mask,warped_images[-1],masks[-1])
            warped_images.append(warped)
            masks.append(mask)
            _emit_progress(progress_callback, "Projecting photos", index, len(images))
        return multiband_blend(warped_images,masks,progress_callback=progress_callback)
