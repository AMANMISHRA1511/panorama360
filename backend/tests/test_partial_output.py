import numpy as np
from app.services.stitch import show_missing_as_blank


def test_unobserved_directions_are_blank_not_stretched():
    image = np.full((12, 24, 3), 160, dtype=np.uint8)
    coverage = np.zeros((12, 24), dtype=np.uint8)
    coverage[:, 8:14] = 255
    result = show_missing_as_blank(image, coverage)
    assert (result[:, 8:14] == image[:, 8:14]).all()
    assert (result[:, :8] == [50, 39, 27]).all()
    assert (result[:, 14:] == [50, 39, 27]).all()


def test_scaled_coverage_mask_preserves_center_content():
    image = np.full((20, 40, 3), 90, dtype=np.uint8)
    coverage = np.zeros((10, 20), dtype=np.uint8)
    coverage[:, 5:15] = 255
    result = show_missing_as_blank(image, coverage)
    assert (result[:, 10:30] == 90).all()
    assert (result[:, :10] == [50, 39, 27]).all()
