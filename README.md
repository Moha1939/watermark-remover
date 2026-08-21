# Watermark Remover

A small Flask web app for removing a fixed-position watermark/logo from a video.
Upload a clip, drag a box over the watermark on the extracted preview frame, and
it runs FFmpeg's `delogo` filter over that region for the whole video.

## How it works

- Upload hits `/api/upload`, which saves the file and extracts the first frame
  with FFmpeg so you can see exactly where to draw the box.
- You drag a rectangle on that frame in the browser (plain canvas math, no
  extra libraries).
- `/api/process` runs:
  ```
  ffmpeg -i input.mp4 -vf delogo=x=X:y=Y:w=W:h=H:show=0 -c:a copy output.mp4
  ```
  `delogo` blends in nearby pixels to paper over the box — it works best when
  the watermark sits in a fixed spot over a fairly static or textured
  background. It won't do full AI inpainting for a moving watermark or a
  busy, changing background behind it (see note below).

## Local setup

```bash
cd watermark-remover
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000. Requires `ffmpeg` and `ffprobe` on your PATH
(`brew install ffmpeg` / `apt install ffmpeg` / etc).

## Deploying so you can use it from your phone

The included `Dockerfile` installs Python + FFmpeg together, so any host that
supports Docker deployments will work (Render, Railway, Fly.io, etc). Render's
free tier is the simplest:

1. Push this folder to a new GitHub repo.
2. Go to https://render.com, sign up/log in, click **New > Web Service**.
3. Connect your GitHub repo.
4. Render should auto-detect the `Dockerfile`. If it asks for a runtime,
   choose **Docker**.
5. Leave the build/start command blank (the Dockerfile handles it).
6. Choose the **Free** instance type, click **Create Web Service**.
7. Wait for the build (a few minutes) — you'll get a URL like
   `https://your-app.onrender.com`. Open that on your phone.

Notes for the free tier:
- It spins down after ~15 min idle, so the first request after a break takes
  ~30–60s to wake up.
- Free disk is ephemeral — uploaded/processed files disappear on redeploy or
  restart, which is fine for a use-once-and-download tool like this.
- If a video processing request takes longer than Render's proxy timeout,
  bump `--timeout 300` in the Dockerfile's `CMD` line, or process shorter
  clips.

## Notes & limits

- **Only handles fixed-position watermarks.** If the logo moves or the video
  is heavily edited/cut, `delogo` will produce visible smudging.
- **500MB upload cap** — adjust `MAX_CONTENT_LENGTH` in `app.py` if needed.
- **No auth/queueing** — this is a single-user local tool. For multi-user or
  production use you'd want a job queue (e.g., Celery/RQ) since FFmpeg
  processing blocks the request thread, plus proper auth and file cleanup.
- **For moving watermarks or complex backgrounds**, `delogo` alone won't cut
  it — you'd need frame-by-frame video inpainting (e.g., ProPainter or
  E2FGVI) instead of a single static filter. Happy to help scaffold that if
  you hit that case.
- Only remove watermarks from content you own or have rights to edit —
  stripping a watermark to redistribute someone else's work is a copyright
  issue regardless of the tool.

## Project structure

```
watermark-remover/
├── app.py              # Flask backend (upload, frame extraction, delogo processing)
├── templates/
│   └── index.html      # Upload UI + canvas region selector
├── requirements.txt
├── uploads/             # incoming videos + preview frames (gitignored contents)
└── outputs/             # processed videos (gitignored contents)
```
