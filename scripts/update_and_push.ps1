# Regenerate stats from your local server files and push to GitHub.
# Usage: .\scripts\update_and_push.ps1
# Requires: paths.json (copy from paths.json.example)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

$PathsFile = Join-Path $RepoRoot "paths.json"
if (-not (Test-Path $PathsFile)) {
    Write-Error "Missing paths.json — copy paths.json.example to paths.json and edit your server paths."
}

$paths = Get-Content $PathsFile -Raw | ConvertFrom-Json
$statsDir = $paths.stats_dir
$logsDir = $paths.logs_dir

Write-Host "Regenerating stats..."
$py = "python"
if (Test-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")) {
    $py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
}

& $py -m pip install -q -r requirements.txt
& $py analyze_stats.py --stats-dir $statsDir --logs-dir $logsDir --output-dir $RepoRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Committing updated data..."
git add player_stats.json player_stats.js player_stats.csv
$status = git status --porcelain
if (-not $status) {
    Write-Host "No changes to publish."
    exit 0
}

$date = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "chore: update player stats ($date)"
git push
Write-Host "Done. GitHub Pages will refresh within a minute or two."
