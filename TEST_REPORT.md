# Build / Test Report

Tests performed on November 13, 2026 in the assistant's isolated build container:

- **Backend:** `PYTHONPATH=backend pytest -q backend/tests` → **16 passed**.
- **Python syntax:** `python -m compileall -q backend` → successful.
- **Frontend JavaScript / JSX syntax:** parsed all `.js` / `.jsx` source files with the TypeScript compiler parser (JS and JSX grammar; there are no TypeScript source files) → **0 syntax diagnostics**.
- **Backend covered:** camera intrinsic and rotation matrices, SO(3) homography recovery, RANSAC feature matches on synthetic rotating imagery, spherical warping/coverage, equirectangular pass-through, boundary seam weld, multi-band blending, deterministic hole filling, non-overlap error, multi-image panorama output, U-Net/SR inference tensor shapes, trained weights save/load from 1-epoch synthetic training, JWT signup/login, password validation, upload, job queue mocking, actual image/video worker processing, private media/gallery isolation, public share/media download, and deletion.
- **Video check:** local FFmpeg + `libx264` transcode succeeded for a short generated test clip, and served the resulting MP4 through FastAPI.

## What was not verified here

- `npm install` could not contact the npm registry (`EAI_AGAIN`); therefore **Vite's final dependency-based build and a browser interaction test were not run**.
- Docker is not present in the build container; therefore **Docker Compose with real MySQL / Redis / frontend server / worker was not end-to-end tested**.
- Hardware camera and device gyroscope behavior was not tested.
- No pretrained weights ship with this project, and generative quality has not been validated. The smoke-tested training script creates baseline checkpoints, not production generative models.

Use the README to run `npm install`, `npm run build`, `docker compose up --build -d`, and the Python tests on your own computer. The project is supplied as source with meaningful automated checks, **not a claim of fully validated production operation**.
