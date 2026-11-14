# Panorama Studio · Full-Stack 360° Photo & Video Web App

React 19 + Vite (JavaScript, not TypeScript), Tailwind CSS v4, Framer Motion, Three.js / React Three Fiber, Axios, React Router, FastAPI, MySQL / SQLAlchemy, Redis, OpenCV, NumPy and PyTorch.

> **Scope:** A functional processing application, not a miracle single-photo 3D reconstruction model. A 2:1 equirectangular photo/video provides a full 360° view; an ordinary perspective photo contains only the directions it captured. Unseen areas can be *approximated* using deterministic interpolation or filled with a custom-trained U-Net, never recovered with factual certainty. The U-Net and super-resolution models ship as **architectures + training code**, *not* pretrained weights. No GPU is required for the classical pipeline.

## 1. Quickest run in VS Code (Docker Compose)

**Requirements:** Docker Desktop with Linux containers enabled, VS Code, available disk/RAM (PyTorch increases the backend image size). Docker Compose v2.

1. Unzip, open `panorama360` in VS Code: **File > Open Folder**.
2. In the VS Code terminal run:

```powershell
Copy-Item .env.example .env
```

3. Edit `.env`: replace the two database passwords and `SECRET_KEY` with private, strong values. The `SECRET_KEY` should be a random string at least 32 bytes long. For example, generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
4. Run:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f backend worker
```

5. Open **http://localhost:5173** (frontend); API docs **http://localhost:8000/docs**; health **http://localhost:8000/health**.
6. Sign up, upload an image (ideally a **2:1** equirectangular panorama) and click **Create my panorama**. The processing page updates via WebSocket; the gallery and viewer appear after processing finishes.
7. Stop/restart:

```powershell
docker compose down
docker compose up -d
```

Data is preserved in named volumes `mysql_data`, `redis_data`, `storage_data`. **Do not** run `docker compose down -v` unless you intend to erase the data.

> Docker local browser URLs are compiled into the frontend at build time. If you change `VITE_API_URL`, rebuild the frontend (`docker compose up --build -d frontend`).

## 2. Run without Docker in VS Code

Install **Python 3.11 or 3.12**, **Node.js 22**, **MySQL 8**, **Redis 7**, **FFmpeg with libx264**, and configure MySQL and Redis to run locally. The frontend is JavaScript only.

Create a database and account in MySQL (example SQL; use your own password):

```sql
CREATE DATABASE panorama360 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'panorama'@'localhost' IDENTIFIED BY 'change-this-password';
GRANT ALL PRIVILEGES ON panorama360.* TO 'panorama'@'localhost';
FLUSH PRIVILEGES;
```

In VS Code **Terminal 1** (PowerShell, project root):

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:DATABASE_URL = 'mysql+pymysql://panorama:change-this-password@127.0.0.1:3306/panorama360'
$env:REDIS_URL = 'redis://localhost:6379/0'
$env:SECRET_KEY = 'replace-this-with-a-long-random-secret-key'
$env:CORS_ORIGINS = 'http://localhost:5173'
$env:PUBLIC_BASE_URL = 'http://localhost:5173'
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In **Terminal 2**, activate the same virtual environment, set the **same** `DATABASE_URL`, `REDIS_URL` and `SECRET_KEY` variables, then:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.worker
```

In **Terminal 3**:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process Bypass` in that terminal, or use `.venv\Scripts\python.exe` directly.

On macOS/Linux replace `py -3.11` with `python3.11`, activate with `source .venv/bin/activate`, and use `export NAME=value` for environment variables. On these systems, `redis-server` or Docker can supply Redis.

`backend/storage/` stores files; `backend/weights/` stores optional checkpoint files. Neither is committed to source control. Startup creates database tables using SQLAlchemy `create_all`; production installations should introduce schema migrations (Alembic) before evolving the models.

## 3. Features and flow

| Page | Route | Behavior |
|---|---|---|
| Landing | `/` | Feature overview, dark/light theme, CTAs |
| Login / signup | `/login` | 7-day signed JWT, scrypt password hashing |
| Upload | `/upload` | Drag/drop JPG/PNG/WEBP, MP4/MOV/WEBM/AVI, thumbnails, five modes, FOV setting |
| Live capture | `/capture` | `getUserMedia`, 8-shot rotation guide, manual progress count, submit overlapping captures |
| Processing | `/processing/:id` | Redis background worker, WebSocket progress and HTTP polling fallback |
| Panorama viewer | `/view/:id` | React Three Fiber sphere, drag, zoom, mobile gyroscope (browser permission), fullscreen, auto-rotation, before/after panel for images |
| Gallery | `/gallery` | Private projects, search, delete, status |
| Public view | `/s/:token` | View-only link usable without an account; public asset |

API endpoints:

```text
POST   /auth/signup
POST   /auth/login
POST   /convert/single        multipart: file, title, fov
POST   /convert/multi         multipart: files (2–16), title, fov
POST   /convert/video         multipart: file, title, fov
POST   /enhance               multipart: file, title
POST   /generate/missing-angles multipart: files (1–16), title, fov
GET    /result/{job_id}
GET    /gallery
DELETE /gallery/{id}
GET    /assets/{job_id}?kind=output|original  [JWT required]
GET    /share/{token}
GET    /share/{token}/asset    [Public]
WS     /ws/progress/{job_id}?token=<JWT>
GET    /health
```

- Images: maximum 100 MiB per file, 16 files per multi-upload; videos: maximum 350 MiB per file.
- Video output: up to **240 decoded output frames**, limited to about **18 FPS**, output **1024×512** H.264 MP4 via FFmpeg; longer inputs are truncated to this cap. Video has **no audio track** in this demo. Use a true equirectangular video for correct 360° fidelity. Non-equirectangular frames are projected and holes interpolated, not transformed into new camera viewpoints.
- Images: output JPG **2048×1024**. The browser can export the same output as PNG. Videos export MP4. Shared media is downloadable.
- Self-hosted: external AI API keys are not required. CUDA is used automatically when PyTorch detects a compatible GPU (GPU container setup is separate; standard Docker image installs a CPU-compatible configuration).

## 4. Exact matrix and image pipeline

Pinhole intrinsic calibration for frame width `w`, height `h` and horizontal FOV `θ`:

```text
f = w / (2 tan(θ/2))
K = [[f,0,(w-1)/2], [0,f,(h-1)/2], [0,0,1]]
Rx = [[1,0,0], [0,cos(rx),-sin(rx)], [0,sin(rx),cos(rx)]]
Ry = [[cos(ry),0,sin(ry)], [0,1,0], [-sin(ry),0,cos(ry)]]
Rz = [[cos(rz),-sin(rz),0], [sin(rz),cos(rz),0], [0,0,1]]
R = Rz @ Ry @ Rx
```

For a destination pixel `(u,v)` in a `W×H` panorama:

```text
longitude = (2(u+0.5)/W - 1) * π
latitude  = (0.5 - (v+0.5)/H) * π
direction = (cos(lat)sin(lon), -sin(lat), cos(lat)cos(lon))
camera    = R @ direction
pixel_homogeneous = K @ camera
source_x = pixel_homogeneous[0] / pixel_homogeneous[2]
source_y = pixel_homogeneous[1] / pixel_homogeneous[2]
```

Only positive camera `z` and in-bounds coordinates count as valid. We inverse-sample with `cv2.remap` and a pixel coverage mask. Geometric code: `backend/app/services/geometry.py`.

For overlapping images, SIFT (or ORB fallback) detects features; BFMatcher KNN with Lowe ratio filtering obtains correspondences; `cv2.findHomography(..., cv2.RANSAC)` estimates a homography. For pure rotation, `H ≈ K_dst @ R_dst @ inv(R_src) @ inv(K_src)` (**K·R·K⁻¹** for equal intrinsics and rotation relative to reference). We project to the closest SO(3) matrix using SVD and accumulate relative rotations for each successive frame. We perform exposure gain compensation in overlapping areas and masked **Laplacian pyramid / Gaussian weight multi-band blending**. Zero-coverage pixels are optionally filled; `wrap_seam` blends a thin periodic border and explicitly equals the first and last pixel columns. Code: `backend/app/services/stitch.py`.

**Model validity:** Rotation-only homography assumes a fixed optical center, limited parallax, and overlapping pictures. Depth differences, motion, low texture and mismatched camera FOV can cause failures. The system returns an explicit failure rather than claiming a correct stitch.

## 5. Optional CNN models and training

`app/ml/networks.py` contains the U-Net inpainting CNN (image + binary missing mask) and a 2× super-resolution CNN (PixelShuffle). `app/ml/inference.py` selects CUDA if available, loads checkpoints from `backend/weights/`, and uses trained models when those weights exist. Without them, holes receive **circular color interpolation** and the image receives **classical detail enhancement**. These are not generative AI.

Provide a collection of your own representative JPG/PNG panoramas inside `backend/training-images/` and run:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python train.py --data ./training-images --epochs 4 --batch-size 2
```

Checkpoints are saved as `weights/inpaint.pt` and `weights/superres.pt`. For Docker reload them using `docker compose restart backend worker`. Training on a handful of images is just a smoke test; substantial, licensed data and careful evaluation are necessary to generate plausible unobserved content. The U-Net only learns from masked input textures and cannot reconstruct true unseen geometry or semantic content.

## 6. Tests and troubleshooting

Backend tests (geometry, rotation order, RANSAC feature recovery, sphere masks, seam weld, multi-band blend, U-Net and SR tensor output, login/signup, upload, worker, private/gallery/share lifecycle):

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q tests
```

The API test uses a temporary SQLite database and mocks the Redis queue, so it does not require MySQL or Redis; it *does* execute the conversion worker against a real example image. For frontend syntax/bundle validation:

```powershell
cd frontend
npm run build
```

Troubleshooting:
- **Cannot reach API:** check `docker compose ps`, CORS origins, and `http://localhost:8000/health`.
- **Job stuck queued:** start/check `worker` and `redis`: `docker compose logs -f worker redis`.
- **Failed to stitch:** overlap photos 25–50%, move around a fixed camera center, avoid blank walls. The default FOV 90° is approximate unless calibrated.
- **Video output fails:** check availability of `ffmpeg` and H.264 encoder `libx264`, or try a readable MP4 video.
- **Camera unavailable:** use `localhost` or HTTPS and grant browser camera permission.
- **No AI realism:** download/train validated model weights yourself. The included checkpoints are intentionally absent.
- **MySQL on Windows:** ensure it listens on `127.0.0.1:3306` and your database credentials match `DATABASE_URL`.
- **npm Tailwind issues:** use Node 22 and `@tailwindcss/vite` plugin with `@import "tailwindcss";` (this project already configures both).

## 7. Short project explanation (for presentation)

> “Panorama Studio is a full-stack React and FastAPI application for creating and sharing immersive 360° photo and video experiences. The frontend handles JWT authentication, uploads, live camera capture and an interactive WebGL sphere viewer. FastAPI stores project metadata in MySQL and queues work through Redis, allowing a separate Python worker to report progress over WebSockets. The core computer-vision pipeline converts longitude and latitude pixels into 3D directions, rotates them with camera matrices, and samples original images using OpenCV. For multiple images, it detects overlapping features, estimates rotational homographies with RANSAC, performs spherical warping and multi-band blending, then welds the seam. Optional PyTorch U-Net and super-resolution models can perform learned refinement when custom-trained weights are supplied. Projects remain private until users open a public share link.”

## 8. Before production

Add upload malware scanning / content sniffing beyond decoding, upload and request rate limits, reverse-proxy HTTPS, secrets management, worker job retry/timeout policies, Alembic migrations, Redis/WebSocket scaling, observability, bounded storage with quotas, authenticated share token revocation, background deletion/cleanup, GPU-specific images and benchmarks, dedicated video streaming with range requests, and trained/validated model checkpoints. The sample provides functional development architecture, not an audited production deployment.
