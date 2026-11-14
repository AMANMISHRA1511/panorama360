import cv2
import numpy as np
import pytest
from app.services.geometry import (intrinsic_matrix, rotation_xyz, spherical_warp,
                                   rotation_from_homography, feature_match_rotation)
from app.services.stitch import (wrap_seam, to_panorama, stitch_images,
                                 multiband_blend, fill_missing_deterministic)


def test_intrinsics_and_exact_rotation_order():
    k = intrinsic_matrix(800, 600, 90)
    assert k[0, 0] == pytest.approx(400)
    assert k[1, 1] == pytest.approx(400)
    rx, ry, rz = .2, -.3, .4
    from math import sin, cos
    x = np.array([[1,0,0],[0,cos(rx),-sin(rx)],[0,sin(rx),cos(rx)]])
    y = np.array([[cos(ry),0,sin(ry)],[0,1,0],[-sin(ry),0,cos(ry)]])
    z = np.array([[cos(rz),-sin(rz),0],[sin(rz),cos(rz),0],[0,0,1]])
    assert np.allclose(rotation_xyz(rx, ry, rz), z @ y @ x)
    assert np.allclose(rotation_xyz(rx, ry, rz).T @ rotation_xyz(rx, ry, rz), np.eye(3))


def test_homography_recovers_rotation():
    k = intrinsic_matrix(1200, 800)
    r = rotation_xyz(.05, .18, -.01)
    h = k @ r.T @ np.linalg.inv(k) # maps current -> previous
    recovered = rotation_from_homography(h, k, k)
    assert np.allclose(recovered, r, atol=1e-8)


def test_spherical_center_faces_forward_and_masks_back():
    picture = np.full((200, 300, 3), (12, 70, 220), np.uint8)
    result, mask = spherical_warp(picture, np.eye(3), (512, 256))
    assert mask[128, 256] == 255
    assert tuple(result[128, 256]) == (12, 70, 220)
    assert mask[128, 0] == 0
    assert mask[0, 256] == 0


def test_equirectangular_passthrough_and_pixel_weld():
    picture = np.zeros((100,200,3),np.uint8)
    picture[:, :100] = (0, 0, 255)
    picture[:, 100:] = (255, 0, 0)
    panorama, mask = to_panorama(picture, (512, 256))
    assert np.all(mask==255)
    result = wrap_seam(panorama)
    assert np.array_equal(result[:,0], result[:,-1])


def test_circular_hole_fill_does_not_change_valid_pixels():
    image=np.zeros((12,20,3),np.uint8)
    image[:,4:8] = (11,22,33)
    mask=np.zeros((12,20),np.uint8)
    mask[:,4:8]=255
    output=fill_missing_deterministic(image,mask)
    assert np.array_equal(output[mask!=0],image[mask!=0])
    assert output[:,0].mean()>0
    assert np.array_equal(wrap_seam(output)[:,0],wrap_seam(output)[:,-1])


def test_multiband_composite_output_and_mask():
    first=np.full((128,256,3),50,np.uint8)
    second=np.full((128,256,3),150,np.uint8)
    ma=np.zeros((128,256),np.uint8);ma[:,:170]=255
    mb=np.zeros((128,256),np.uint8);mb[:,90:]=255
    output,mask=multiband_blend([first,second],[ma,mb])
    assert output.shape==(128,256,3)
    assert mask.min()==255
    assert 49 <= output[:,10].mean() <= 55
    assert 145 <= output[:,245].mean() <= 151


def test_nonoverlap_fails_explicitly():
    pictures=[np.zeros((128,256,3),np.uint8),np.zeros((128,256,3),np.uint8)]
    with pytest.raises(ValueError, match='visual features|overlap'):
        stitch_images(pictures,(512,256))


def test_feature_matching_recovers_synthetic_camera_yaw():
    rng = np.random.default_rng(44)
    prev = rng.integers(10, 245, size=(480, 640, 3), dtype=np.uint8)
    prev = cv2.GaussianBlur(prev, (3, 3), 0.3)
    yaw = np.deg2rad(8)
    r = rotation_xyz(0, yaw, 0)
    k = intrinsic_matrix(640, 480)
    current = cv2.warpPerspective(prev, k @ r @ np.linalg.inv(k), (640, 480))
    estimated = feature_match_rotation(prev, current)
    assert np.allclose(estimated, r, atol=.04)


def test_two_overlapping_photos_stitch_to_sphere():
    rng = np.random.default_rng(64)
    base = rng.integers(16, 240, size=(360, 540, 3), dtype=np.uint8)
    base = cv2.GaussianBlur(base, (3, 3), .3)
    k = intrinsic_matrix(540, 360)
    yaw = rotation_xyz(0, np.deg2rad(14), 0)
    next_image = cv2.warpPerspective(base, k @ yaw @ np.linalg.inv(k), (540,360))
    panorama, coverage = stitch_images([base, next_image], (512, 256))
    assert panorama.shape == (256, 512, 3)
    assert coverage.shape == (256, 512)
    assert coverage[128,256] == 255
    assert int(coverage.sum()) > 255 * 3000
