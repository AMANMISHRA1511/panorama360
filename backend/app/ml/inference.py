import logging
from functools import lru_cache

import cv2
import numpy as np
import torch

from app.config import WEIGHTS_DIR
from app.ml.networks import UNetInpaint, SuperResolutionCNN
from app.services.stitch import fill_missing_deterministic

log = logging.getLogger(__name__)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def weights_state():
    """File presence only; does not imply good or fully trained weights."""
    return {
        "device": str(DEVICE),
        "inpaint_trained": (WEIGHTS_DIR / "inpaint.pt").is_file(),
        "superres_trained": (WEIGHTS_DIR / "superres.pt").is_file(),
    }


@lru_cache(maxsize=2)
def _load_cached(model_class, filename, modification_ns):
    """Reuse weights between jobs; modification time reloads changed files."""
    path = WEIGHTS_DIR / filename
    model = model_class().to(DEVICE)
    state_dict = torch.load(path, map_location=DEVICE, weights_only=True)
    model.load_state_dict(state_dict, strict=True)
    model.eval()
    return model


def load_trained(model_class, filename):
    path = WEIGHTS_DIR / filename
    if not path.is_file():
        return None
    try:
        return _load_cached(model_class, filename, path.stat().st_mtime_ns)
    except (RuntimeError, ValueError, OSError, KeyError, TypeError) as exc:
        log.warning("Ignoring invalid or incompatible model weights at %s: %s", path, exc)
        return None


def _validate_image(image):
    if not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Expected an H x W x 3 BGR NumPy image")
    if image.dtype != np.uint8 or min(image.shape[:2]) < 1:
        raise ValueError("Image must have uint8 pixels and nonzero dimensions")


def _to_tensor(bgr):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return torch.from_numpy(np.ascontiguousarray(rgb.transpose(2, 0, 1)))[None].to(
        DEVICE, dtype=torch.float32
    ) / 255.0


def _to_bgr(prediction):
    rgb = (prediction.detach().cpu().clamp(0, 1)[0].permute(1, 2, 0).numpy() * 255).round().astype(np.uint8)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def inpaint_panorama(image, coverage):
    """Fill missing panorama pixels; return (BGR image, method label).

    If no compatible model weights exist, use interpolation. Neither method
    can reliably reconstruct unseen camera directions without appropriate data.
    """
    _validate_image(image)
    if not isinstance(coverage, np.ndarray) or coverage.shape != image.shape[:2]:
        raise ValueError("Coverage must be an H x W mask matching the image")

    holes = coverage == 0
    if not np.any(holes):
        return image.copy(), "complete"

    model = load_trained(UNetInpaint, "inpaint.pt")
    if model is None:
        return fill_missing_deterministic(image, coverage), "deterministic-fill"

    height, width = image.shape[:2]
    reduced = cv2.resize(image, (512, 256), interpolation=cv2.INTER_AREA)
    reduced_mask = cv2.resize(holes.astype(np.uint8), (512, 256), interpolation=cv2.INTER_NEAREST)
    mask_tensor = torch.from_numpy(reduced_mask[None, None].copy()).to(DEVICE, dtype=torch.float32)

    with torch.inference_mode():
        prediction = model(_to_tensor(reduced), mask_tensor)
    restored = cv2.resize(_to_bgr(prediction), (width, height), interpolation=cv2.INTER_CUBIC)

    result = image.copy()
    result[holes] = restored[holes]  # Never overwrite photographed pixels.
    return result, "trained-unet"


def enhance_panorama(image):
    """Apply learned 2x SR when weights exist; otherwise classical enhancement."""
    _validate_image(image)
    model = load_trained(SuperResolutionCNN, "superres.pt")
    if model is None:
        return cv2.detailEnhance(image, sigma_s=8, sigma_r=0.12), "classical-detail-enhancement"

    reduced = cv2.resize(image, (1024, 512), interpolation=cv2.INTER_AREA)
    with torch.inference_mode():
        prediction = model(_to_tensor(reduced))
    return _to_bgr(prediction), "trained-super-resolution"
