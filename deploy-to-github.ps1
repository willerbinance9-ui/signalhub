# Push AARE Signal Hub to GitHub
# Run from this folder:  .\deploy-to-github.ps1

$ErrorActionPreference = "Stop"
$RemoteUrl = "https://github.com/willerbinance9-ui/signalhub.git"

$git = "git"
if (Test-Path "C:\Program Files\Git\cmd\git.exe") {
    $git = "C:\Program Files\Git\cmd\git.exe"
} elseif (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git is not installed. Install from https://git-scm.com/download/win then re-run this script."
}

Set-Location $PSScriptRoot

if (-not (Test-Path ".git")) {
    & $git init
}

& $git add .
$status = & $git status --porcelain
if ($status) {
    & $git commit -m "Initial AARE Signal Hub - FastAPI ingest API for Render and Quantum MT5 execution"
}

& $git remote get-url origin 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    & $git remote set-url origin $RemoteUrl
} else {
    & $git remote add origin $RemoteUrl
}

& $git branch -M main
& $git push -u origin main

Write-Host "Done. Repo: $RemoteUrl"
