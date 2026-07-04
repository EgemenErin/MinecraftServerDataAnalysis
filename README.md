# MC Stats Dashboard

Static dashboard for a Fabric Minecraft server — player stats, quest progress, boss kills, awards, and more.

## Privacy warning

Publishing this repo (especially `player_stats.json`) makes **player names, stats, and death log messages public**. Use a **private repo** if you only want invited viewers, or strip/redact sensitive fields before pushing.

## Quick start (local)

```powershell
cd mc-stats-dashboard
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy paths.json.example paths.json
# edit paths.json with your server folders

python analyze_stats.py --stats-dir "PATH\world\stats" --logs-dir "PATH\logs"
# open dashboard.html in a browser
```

## Publish to GitHub + auto-update nightly

GitHub's cloud runners **cannot** read files on your PC. The server data stays local; a **scheduled task on your machine** regenerates stats and pushes the updated JSON/JS to GitHub. GitHub Pages then serves the site.

### 1. Create the repo

```powershell
cd C:\Users\egeme\Desktop\aaaa\mc-stats-dashboard
git init
git add .
git commit -m "Initial mc-stats dashboard"
gh repo create mc-stats-dashboard --public --source=. --push
```

Use `--private` instead of `--public` if you don't want stats searchable on GitHub.

### 2. Enable GitHub Pages

In the repo on GitHub: **Settings → Pages → Build and deployment → GitHub Actions**.

The included workflow `.github/workflows/pages.yml` deploys on every push to `main`.

Your site URL will be:

`https://<username>.github.io/mc-stats-dashboard/`

### 3. Configure local paths (not committed)

```powershell
copy paths.json.example paths.json
# edit paths.json
```

### 4. Nightly auto-update (Windows Task Scheduler)

```powershell
# one-time: allow git push (HTTPS token or SSH key configured)
.\scripts\install_nightly_task.ps1
```

Or run manually anytime:

```powershell
.\scripts\update_and_push.ps1
```

Default schedule: **3:00 AM daily** — regenerates stats from your server folder, commits `player_stats.js`, pushes to GitHub, Pages redeploys automatically.

### 5. Share with players

Send them the GitHub Pages link. They just refresh the page after your nightly job runs — no server or Python needed on their side.

## Customize lore & awards

Edit `config.py` — titles, awards, boss entity hints, embarrassing death categories.

## Project layout

| File | Purpose |
|------|---------|
| `analyze_stats.py` | Main processor |
| `dashboard.html` | Dashboard UI |
| `player_stats.js` | Data consumed by the dashboard (auto-generated) |
| `paths.json` | Local server paths (gitignored) |
| `scripts/update_and_push.ps1` | Regenerate + git push |
