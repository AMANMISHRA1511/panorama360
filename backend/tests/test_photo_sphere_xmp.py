import cv2
import numpy as np
import pytest
from app.services.photo_sphere_xmp import add_photo_sphere_xmp, XMP_HEADER


def test_photo_sphere_export_has_xmp_and_decodes(tmp_path):
    path = tmp_path / 'sphere.jpg'
    pixels = np.zeros((48, 96, 3), dtype=np.uint8)
    pixels[:] = (90, 110, 180)
    assert cv2.imwrite(str(path), pixels)
    add_photo_sphere_xmp(path, 96, 48)
    content = path.read_bytes()
    assert content.startswith(b'\xff\xd8')
    assert XMP_HEADER in content
    assert b'GPano:ProjectionType="equirectangular"' in content
    assert b'GPano:FullPanoWidthPixels="96"' in content
    assert cv2.imread(str(path)).shape == pixels.shape


def test_photo_sphere_export_rejects_non_2_to_1(tmp_path):
    path = tmp_path / 'not-pano.jpg'
    path.write_bytes(b'\xff\xd8\xff\xd9')
    with pytest.raises(ValueError, match='2:1'):
        add_photo_sphere_xmp(path, 100, 70)


def test_photo_sphere_export_rejects_non_jpeg(tmp_path):
    path = tmp_path / 'false.jpg'
    path.write_bytes(b'not JPEG')
    with pytest.raises(ValueError, match='JPEG'):
        add_photo_sphere_xmp(path, 100, 50)


def test_live_capture_plan_has_32_targets_and_upload_limit():
    from app.routers import jobs
    from app.services import stitch
    from pathlib import Path
    source = Path(__file__).parents[2] / 'frontend' / 'src' / 'pages' / 'Capture.jsx'
    # Patch includes three rings of eight plus 8 pole shots, and permits 32 images.
    assert 'FULL_CAPTURE_STEPS' in source.read_text(encoding='utf-8')
    assert '32 shots' in source.read_text(encoding='utf-8')
    assert 'len(files) <= 32' in Path(jobs.__file__).read_text(encoding='utf-8')
    assert 'len(images) <= 32' in Path(stitch.__file__).read_text(encoding='utf-8')


def test_api_accepts_32_live_frames(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.database import Base, engine
    from app.main import app
    from app.routers import jobs
    monkeypatch.setattr(jobs, 'STORAGE_DIR', tmp_path)
    queued = []
    monkeypatch.setattr(jobs, 'enqueue', queued.append)
    Base.metadata.create_all(bind=engine)
    image = np.full((80, 144, 3), 125, dtype=np.uint8)
    ok, buf = cv2.imencode('.jpg', image)
    assert ok
    with TestClient(app) as client:
        signup = client.post('/auth/signup', json={
            'email': 'capture-32-test@example.com', 'password': 'securepass123',
        })
        assert signup.status_code == 201, signup.text
        headers = {'Authorization': 'Bearer ' + signup.json()['access_token']}
        parts = [('files', (f'frame-{i}.jpg', buf.tobytes(), 'image/jpeg')) for i in range(32)]
        response = client.post('/convert/multi', files=parts, data={'fov': '90', 'ai_enabled': 'false'}, headers=headers)
        assert response.status_code == 202, response.text
        assert len(queued) == 1
