"""Conservative, opt-in enhancement for real panorama pixels.

No changes are made by default. AI enhancement is blended gently into only
observed pixels. At the user's request, *small, fully surrounded holes* may be
filled; unphotographed directions are never inferred to be real camera views.
"""
import logging

import cv2
import numpy as np

log = logging.getLogger(__name__)

MAX_AI_STRENGTH = 0.25


def small_internal_holes(coverage: np.ndarray, *, max_area_fraction=0.001) -> np.ndarray:
    """Find tiny missing components surrounded by photographic coverage.

    Never fill components touching any of the four image borders. Reject
    components larger than 0.1% of the panorama or wider/taller than 64px.
    """
    if coverage.ndim != 2:
        raise ValueError("Coverage must be HxW")
    gaps = (coverage == 0).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(gaps, 8)
    height, width = gaps.shape
    area_limit = max(1, int(height * width * max_area_fraction))
    accepted = np.zeros_like(gaps, dtype=np.uint8)
    for component in range(1, count):
        x, y, w, h, area = [int(v) for v in stats[component]]
        if (area > area_limit or w > 64 or h > 64 or x == 0 or y == 0 or
                x + w >= width or y + h >= height):
            continue
        accepted[labels == component] = 255
    return accepted


def apply_optional_ai(image: np.ndarray, coverage: np.ndarray, *, enabled=False,
                      strength=0.12, fill_small_gaps=False):
    """Return (processed_BGR, display_coverage, processing_description).

    Coverage describes photographed pixels; the separately returned display
    coverage also includes explicitly permitted small repaired gaps.
    Strength is deliberately limited to 0...0.25 to avoid stylizing photos.
    """
    if (not isinstance(image, np.ndarray) or image.ndim != 3 or
            image.shape[2] != 3 or image.dtype != np.uint8):
        raise ValueError("Expected a uint8 BGR photograph")
    if not isinstance(coverage, np.ndarray) or coverage.shape != image.shape[:2]:
        raise ValueError("Coverage dimensions must match the image")
    if not 0 <= float(strength) <= MAX_AI_STRENGTH:
        raise ValueError("AI strength must be between 0 and 0.25")

    result = image.copy()
    display_coverage = (coverage > 0).astype(np.uint8) * 255
    if not enabled:
        return result, display_coverage, "AI off — original pixels preserved"

    alpha = float(strength)
    method = "AI intensity 0%"
    if alpha > 0:
        # Import lazily so disabled AI never loads PyTorch or reads weights.
        from app.ml.inference import enhance_panorama
        try:
            enhanced, method = enhance_panorama(image)
        except Exception as exc:
            log.warning("Enhancement model unavailable; using mild classical filter: %s", exc)
            enhanced = cv2.detailEnhance(image, sigma_s=8, sigma_r=0.08)
            method = "mild classical fallback"
        if enhanced.shape[:2] != image.shape[:2]:
            enhanced = cv2.resize(enhanced, (image.shape[1], image.shape[0]),
                                  interpolation=cv2.INTER_AREA)
        if enhanced.shape != image.shape or enhanced.dtype != np.uint8:
            raise ValueError("Enhancement returned an invalid image")
        blend = cv2.addWeighted(image, 1.0 - alpha, enhanced, alpha, 0)
        valid = coverage > 0
        result[valid] = blend[valid]

    gap_count = 0
    if fill_small_gaps:
        small_mask = small_internal_holes(coverage)
        gap_count = int(np.count_nonzero(small_mask))
        if gap_count:
            from app.ml.inference import inpaint_panorama, weights_state
            try:
                if weights_state()["inpaint_trained"]:
                    # Mask 0 means inpaint requested, 255 means preserve.
                    model_coverage = np.where(small_mask > 0, 0, 255).astype(np.uint8)
                    filled, _ = inpaint_panorama(result, model_coverage)
                else:
                    # Untrained models never hallucinate surrounding content.
                    filled = cv2.inpaint(result, small_mask, 3, cv2.INPAINT_TELEA)
            except Exception as exc:
                log.warning("Small-gap model failed; using classical inpainting: %s", exc)
                filled = cv2.inpaint(result, small_mask, 3, cv2.INPAINT_TELEA)
            result[small_mask > 0] = filled[small_mask > 0]
            display_coverage[small_mask > 0] = 255

    return result, display_coverage, f"{method}; {gap_count} small gap pixels filled"
