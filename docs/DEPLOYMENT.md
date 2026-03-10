# Deployment

This document covers a simple demo deployment for ECC Sheet on a Linux server.

## Recommended Demo Layout

- App path: `/opt/ecc-sheet`
- Service user: `eccsheet`
- App server: Gunicorn on `127.0.0.1:5000`
- Reverse proxy: Caddy or Nginx
- Database: SQLite in `instance/ecc_sheet.db`

## Copy the Repo Over SSH

If you want to copy your local working tree instead of cloning on the server,
use [../scripts/copy_repo_via_ssh.sh](../scripts/copy_repo_via_ssh.sh).

```bash
./scripts/copy_repo_via_ssh.sh root@your-server /opt/ecc-sheet
```

Useful variants:

- Include the local `.env` file:
  `./scripts/copy_repo_via_ssh.sh root@your-server /opt/ecc-sheet --include-env`
- Include the local `instance/` directory and SQLite DB for a demo copy:
  `./scripts/copy_repo_via_ssh.sh root@your-server /opt/ecc-sheet --include-instance`
- Make the remote directory match local exactly:
  `./scripts/copy_repo_via_ssh.sh root@your-server /opt/ecc-sheet --delete`

By default the script excludes `.git`, `.venv`, `node_modules`, logs, caches,
and `.env`.

## Server Setup

Run these commands on the server after the files are copied:

For a demo, the commands below use vendor `curl | sh` installers for `uv` and
`bun`. For production, prefer official package managers or signed binary
releases from the vendor site instead of piping installers directly to a shell.
If you do use the installer scripts, verify the published checksums or GPG
signatures from the vendor's release page first and review the installer before
running it.

```bash
sudo useradd --system --home-dir /opt/ecc-sheet --shell /usr/sbin/nologin eccsheet || true
sudo chown -R eccsheet:eccsheet /opt/ecc-sheet

sudo apt update
sudo apt install -y curl rsync build-essential

sudo -u eccsheet bash -lc '
  cd /opt/ecc-sheet
  curl -LsSf https://astral.sh/uv/install.sh | sh
  curl -fsSL https://bun.sh/install | bash
  export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"
  uv python install 3.13
  uv venv --python 3.13
  source .venv/bin/activate
  uv sync
  uv pip install gunicorn
  bun install
  bun run build
'
```

## Environment File

Create `/opt/ecc-sheet/.env`. For the demo access model you described:

```env
SECRET_KEY=replace-with-a-random-secret
DATABASE_URL=sqlite:////opt/ecc-sheet/instance/ecc_sheet.db
USER_NAME=Razvan Azamfirei
AUTH_PROXY_USERNAME_HEADER=X-Auth-User
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax

ADMIN_USERS=Razvan Azamfirei
PAYROLL_ADMIN_USERS=Razvan Azamfirei
REPORT_VIEW_ALL_USERS=*

AMION_SCHEDULE_CODE=<your_schedule_code>
TIMEZONE=America/New_York
FLASK_ENV=production
PORT=5000  # Used for local/non-systemd runs; the systemd unit binds 127.0.0.1:5000 directly
```

What this does:

- Any authenticated demo user can pick any resident on the reports page.
- Only `Razvan Azamfirei` gets billing, payroll, email, admin, and audit access.
- The reverse proxy tells Flask who the current user is using `X-Auth-User`.
- `AMION_SCHEDULE_CODE` overrides the default in `backend/config.py` so schedule and staff imports target your intended Amion schedule.
- The reverse proxy must enforce authentication and set `X-Auth-User`; if that header is absent, `backend/auth.py:get_current_user()` returns an empty username rather than Flask rejecting the request on its own.

## Install the systemd Service

The repo includes [../deploy/systemd/ecc-sheet.service](../deploy/systemd/ecc-sheet.service).

Install it like this:

```bash
sudo cp /opt/ecc-sheet/deploy/systemd/ecc-sheet.service /etc/systemd/system/ecc-sheet.service
sudo systemctl daemon-reload
sudo systemctl enable --now ecc-sheet
```

Useful service commands:

```bash
sudo systemctl status ecc-sheet
sudo journalctl -u ecc-sheet -f
sudo systemctl restart ecc-sheet
```

The unit runs:

- `flask db upgrade`
- `python -c "from backend.app import init_db; init_db()"`
- `gunicorn --workers 2 --bind 127.0.0.1:5000 backend.app:app`

on each start, so schema changes and default seeded data stay aligned.

## Reverse Proxy Notes

Your reverse proxy should:

- Require authentication for the demo
- Pass the authenticated username to Flask via `X-Auth-User`
- Overwrite any client-supplied `X-Auth-User`, `X-Forwarded-For`, and `X-Real-IP`
- Proxy traffic to `127.0.0.1:5000`

If you use Caddy, that is the same pattern described in the root
[README](../README.md).
