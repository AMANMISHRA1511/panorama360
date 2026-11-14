"""Tests for the optional, conservative AI controls."""

import numpy as np
import pytest

from app.services.ai_controls import apply_optional_ai, small_internal_holes


def test_off_is_byte_for_byte_original():
    image = np.arange(60 * 120 * 3, dtype=np.uint32).reshape(60, 120, 3).astype(np.uint8)
    coverage = np.zeros((60, 120), np.uint8)
    coverage[10:50, 20:100] = 255
    output, display, message = apply_optional_ai(image, coverage)
    assert np.array_equal(image, output)
    assert np.array_equal(display, coverage)
    assert 'off' in message.lower()


def test_ai_blends_only_valid_pixels(monkeypatch):
    from app.ml import inference
    monkeypatch.setattr(inference, 'enhance_panorama',
                        lambda image: (np.full_like(image, 255), 'test enhancement'))
    image = np.full((32, 64, 3), 100, np.uint8)
    coverage = np.zeros((32, 64), np.uint8)
    coverage[:, 10:40] = 255
    output, display, _ = apply_optional_ai(image, coverage, enabled=True, strength=0.2)
    assert np.array_equal(display, coverage)
    assert (output[:, :10] == 100).all()
    assert (output[:, 40:] == 100).all()
    assert (output[:, 10:40] == 131).all()


def test_only_tiny_enclosed_holes_are_filled(monkeypatch):
    from app.ml import inference
    monkeypatch.setattr(inference, 'enhance_panorama',
                        lambda image: (image.copy(), 'identity'))
    monkeypatch.setattr(inference, 'weights_state', lambda: {'inpaint_trained': False})
    image = np.full((200, 300, 3), 140, np.uint8)
    coverage = np.full((200, 300), 255, np.uint8)
    coverage[80:84, 120:124] = 0  # tiny internal gap
    image[80:84, 120:124] = 0
    out, display, _ = apply_optional_ai(image, coverage, enabled=True,
                                        strength=0.0, fill_small_gaps=True)
    assert (display[80:84, 120:124] == 255).all()
    assert out[80:84, 120:124].mean() > 100
    assert (out[coverage > 0] == image[coverage > 0]).all()


def test_outside_and_large_missing_area_are_never_filled(monkeypatch):
    from app.ml import inference
    monkeypatch.setattr(inference, 'enhance_panorama',
                        lambda image: (image.copy(), 'identity'))
    image = np.full((200, 300, 3), 140, np.uint8)
    coverage = np.zeros((200, 300), np.uint8)
    coverage[40:160, 30:270] = 255
    # huge gaps outside center remain missing
    out, display, _ = apply_optional_ai(image, coverage, enabled=True,
                                        strength=0, fill_small_gaps=True)
    assert np.array_equal(out, image)
    assert np.array_equal(display, coverage)
    assert not small_internal_holes(coverage).any()


def test_ai_limits_enforced():
    image = np.zeros((50, 100, 3), np.uint8)
    coverage = np.full((50, 100), 255, np.uint8)
    with pytest.raises(ValueError, match='AI strength'):
        apply_optional_ai(image, coverage, enabled=True, strength=.99)
    with pytest.raises(ValueError, match='Coverage'):
        apply_optional_ai(image, np.ones((25, 100), np.uint8))
