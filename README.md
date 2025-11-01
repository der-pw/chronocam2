# ChronoCam2

A concise, GitHub-ready scaffold for the ChronoCam2 project. This adds repository hygiene (README, license, .gitignore) and optional CI. Update the placeholders below to match your app.

## Overview
ChronoCam2 is a tool for automatically capturing images from a webcam at regular intervals. Users can define the recording schedule — including specific days, time ranges, or daylight-only operation — making it ideal for outdoor time-lapse documentation, such as construction site monitoring. Its primary purpose is to simplify long-term visual tracking by automating image capture and organization.

## Project Layout
- `app/` — Application code
- `app/config.json` — Runtime configuration

## Quickstart
- Prerequisites: Python 3.10+
- Download project
  ```
  git clone https://github.com/der-pw/chronocam2.git
  cd chronocam2
  ```
- Create a virtual environment
  - Windows PowerShell: `py -3 -m venv .venv && .venv\\Scripts\\Activate.ps1`
  - macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`
- Install dependencies: `python -m pip install -r requirements.txt`

## Run (API + Web UI)
- Development (auto-reload): `uvicorn app.main:app --reload --port 8000`
- Production (example): `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Open: http://127.0.0.1:8000/

### Endpoints
- `GET /` — Dashboard (templates + static)

- `GET /events` — Server-Sent Events for live updates
- `GET /status` — JSON status for UI
- `POST /update` — Save settings (form submit)
- `POST /action/{pause|resume|snapshot}` — Control actions

## Configuration
- File: `app/config.json`
- Keys (subset):
  - `cam_url`: string; webcam snapshot URL
  - `username` / `password`: optional, for `basic`/`digest` auth
  - `auth_type`: `none` | `basic` | `digest`
  - `save_path`: directory to store snapshots (default `./data`)
  - `interval_seconds`: polling interval for snapshots
  - `active_start` / `active_end`: HH:MM window for activity
  - `active_days`: list like `["Mon", "Tue", ...]`
  - `use_astral`: bool; restrict by sunrise/sunset
  - `city_lat` / `city_lon` / `city_tz`: location settings
  - `language`: `de` or `en` (templates/i18n)


## License
This project uses the MIT License. See `LICENSE` for details. If you prefer a different license (Apache-2.0, GPL-3.0, etc.), replace the file accordingly.

## Notes
- Form handling requires `python-multipart` (included in `requirements.txt`).
- Static files are served from `app/static`; templates from `app/templates`.
- On Windows, timezone data may require `tzdata` (included via marker).
