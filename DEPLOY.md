# Running the backend on boot (Raspberry Pi)

This walks through a **systemd** unit so Uvicorn comes up when the Pi boots. Same idea works on other Linux boxes; just fix the paths.

## Before you enable the service

**Python** — Use a venv in the project folder and install deps:

```bash
cd /path/to/Backend
python3 -m venv venv
source venv/bin/activate   # or `venv\Scripts\activate` on Windows when developing
pip install -r requirements.txt
```

**Postgres** — Create a database (the default config expects something like `maintenance` on localhost). Put the real URL in `.env` as `DATABASE_URL`.

**`.env`** — The app reads `PLC_HOST`, `DATABASE_URL`, `SCHEDULER_ENABLED`, retention/analysis intervals, SMTP if you use email alerts, etc. See `app/config.py` for the full set. For a field Pi you almost always want **`TESTING` unset or `0`** so you get the real PLC poll loop and Postgres, not the SQLite + synthetic demo mode.

On first startup the app runs SQLAlchemy `create_all`, then **`sync_tables_for_all_devices`**, which creates the per-device reading/prediction/archive tables (`device_{id}_*`) for every row already in `devices`. If you add devices later (API or `seed_devices.py`), new tables are created when those devices are created or on the next process start. There’s no Alembic in this repo yet, so plan schema changes on Postgres manually or add migrations when you outgrow `create_all`.

**Network** — The Pi needs to reach the PLC at `PLC_HOST` and Postgres at whatever host is in `DATABASE_URL`.

When the process is up, APScheduler runs **unless** `SCHEDULER_ENABLED` is off or `TESTING` is on: periodic analysis (default every 15 minutes) and a daily retention job that archives old readings per device.

## 1. Edit the unit file paths

Open `deploy/capstone-backend.service` and line it up with your machine:

- **WorkingDirectory** — Full path to this Backend repo.
- **Environment PATH** — That path plus `venv/bin` so the service finds Python and Uvicorn.
- **ExecStart** — Full path to `venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000` (change the port here if you need to).
- **User** / **Group** — Account that should own the process (often `pi` on a Raspberry Pi).

If everything lives under `/opt/capstone/Backend` instead, update all of those consistently.

## 2. Install and enable systemd

```bash
sudo cp /home/pi/PROJECTS/Capstone/Backend/deploy/capstone-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable capstone-backend.service
sudo systemctl start capstone-backend.service
```

(`start` is optional if you’re fine waiting until the next reboot.)

## 3. Logs and sanity checks

```bash
sudo systemctl status capstone-backend.service
sudo journalctl -u capstone-backend.service -f
```

Hit `http://<pi-ip>:8000/docs` or the health route from another machine to confirm the API is listening.

## 4. Commands you’ll use again

| Command | What it does |
|--------|----------------|
| `sudo systemctl start capstone-backend.service` | Start now |
| `sudo systemctl stop capstone-backend.service` | Stop |
| `sudo systemctl restart capstone-backend.service` | Reload after code or `.env` changes |
| `sudo systemctl disable capstone-backend.service` | Don’t start on boot |

Systemd accepts the short name `capstone-backend` for these too.

## Postgres password errors

If logs show `password authentication failed for user "postgres"`, the URL doesn’t match the DB role. Example fix:

```bash
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
```

Then set `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/maintenance` in `.env`, or use your own user/password in the same URL shape.

## If the service won’t start after Postgres

The unit file says `After=network-online.target postgresql.service`. If your distro names the service differently (or you use Docker for Postgres), tweak or drop the `postgresql.service` bit so systemd isn’t waiting on the wrong unit.

---

For day-to-day development and pytest, see **TESTING.md**. For architecture and data layout, see **PROJECT_OVERVIEW.md**.
