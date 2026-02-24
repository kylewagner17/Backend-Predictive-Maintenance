# Run the backend on boot (Raspberry Pi)

Use a systemd service so the app and uvicorn start automatically when the Pi boots.

## 1. Adjust paths in the service file

Edit `deploy/capstone-backend.service` and set:

- **WorkingDirectory** – full path to the Backend project on the Pi (e.g. `/home/pi/PROJECTS/Capstone/Backend`).
- **Environment PATH** – same base path, with `/venv/bin` (e.g. `/home/pi/PROJECTS/Capstone/Backend/venv/bin`).
- **ExecStart** – full path to uvicorn in that venv (e.g. `/home/pi/PROJECTS/Capstone/Backend/venv/bin/uvicorn ...`).
- **User** / **Group** – Linux user that owns the project (often `pi`).

If the project or venv lives somewhere else (e.g. `/opt/capstone/Backend`), change all three paths to match.

## 2. Install the service on the Pi

Copy the unit file into systemd and enable it:

```bash
# Copy the service file (use your actual Backend path)
sudo cp /home/pi/PROJECTS/Capstone/Backend/deploy/capstone-backend.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable so it starts on boot
sudo systemctl enable capstone-backend.service

# Start it now (optional; it will also start on next boot)
sudo systemctl start capstone-backend.service
```

## 3. Check status and logs

```bash
# See if it’s running
sudo systemctl status capstone-backend.service

# View recent logs
sudo journalctl -u capstone-backend.service -f
```

## 4. Useful commands

| Command | Purpose |
|--------|--------|
| `sudo systemctl start capstone-backend` | Start the service |
| `sudo systemctl stop capstone-backend` | Stop the service |
| `sudo systemctl restart capstone-backend` | Restart after code or .env changes |
| `sudo systemctl disable capstone-backend` | Stop it from starting on boot |

## Prerequisites on the Pi

- **Python 3** and a **venv** in the Backend folder with `pip install -r requirements.txt`.
- **PostgreSQL** installed and the `maintenance` database created; `.env` (or env) must have a correct `DATABASE_URL`.
- **.env** in the Backend directory so the app loads `PLC_HOST`, `DATABASE_URL`, etc. on startup.

The service starts after the network and PostgreSQL (`After=network-online.target postgresql.service`). If PostgreSQL is not installed as a systemd service or has a different name, remove or change `postgresql.service` in the unit file.
