<#
.SYNOPSIS
    Operations Manager for Open Estate Dashboard.
.DESCRIPTION
    Every command targets exactly one dataset. There is no default: choosing
    the wrong estate by omission is the mistake this script exists to prevent.
    Datasets are defined by datasets/<name>.env - see datasets/README.md.
.EXAMPLE
    .\ops.ps1                                    (Interactive Menu)
    .\ops.ps1 -Dataset demo -Run update          (Rebuild & restart)
    .\ops.ps1 -Dataset demo -Run wipe            (Wipe & Reset DB)
    .\ops.ps1 -Dataset demo -Run seed -File seed.py
#>

param (
    [string]$Dataset = "",
    [string]$Run = "",
    [string]$File = ""
)

# --- 0. DATASET SELECTION ---------------------------------------------------
function Get-Datasets {
    if (-not (Test-Path "datasets")) { return @() }
    Get-ChildItem "datasets/*.env" -ErrorAction SilentlyContinue |
        ForEach-Object { $_.BaseName }
}

if (-not $Dataset) {
    $Available = Get-Datasets
    if ($Available.Count -eq 0) {
        Write-Host "No datasets defined yet." -ForegroundColor Red
        Write-Host "Copy datasets/demo.env.example to datasets/demo.env and edit it."
        exit 1
    }
    Write-Host ""
    Write-Host "Which dataset?" -ForegroundColor Cyan
    $Available | ForEach-Object { Write-Host "  - $_" }
    Write-Host ""
    $Dataset = Read-Host "Dataset name"
}

$EnvFile = "datasets/$Dataset.env"
if (-not (Test-Path $EnvFile)) {
    Write-Host "No such dataset: $EnvFile" -ForegroundColor Red
    exit 1
}

# Compose reads this one file for both interpolation and the container's env.
$Compose = @("compose", "--env-file", $EnvFile)

# A dataset holding real data refuses the destructive commands outright.
$IsProtected = (Select-String -Path $EnvFile -Pattern '^DATASET_PROTECTED=1' -Quiet)
$Label = (Select-String -Path $EnvFile -Pattern '^DATASET_LABEL=(.*)$').Matches.Groups[1].Value

function Assert-NotProtected {
    if ($IsProtected) {
        Write-Host ""
        Write-Host "REFUSED: '$Dataset' is marked DATASET_PROTECTED=1 - it holds real data." -ForegroundColor Red
        Write-Host "Take a backup from the Settings page first, then clear the flag by hand." -ForegroundColor Yellow
        exit 1
    }
}

# --- 1. INTERACTIVE MENU MODE ---
if (-not $Run) {
    Clear-Host
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "      OPEN ESTATE - OPS MANAGER       " -ForegroundColor White
    Write-Host "======================================" -ForegroundColor Cyan
    if ($IsProtected) {
        Write-Host "  DATASET: $Dataset  [PROTECTED - REAL DATA]" -ForegroundColor Yellow
    } else {
        Write-Host "  DATASET: $Dataset  $Label" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "  1. Update  " -NoNewline -ForegroundColor Green
    Write-Host " (Rebuild container & restart)"

    Write-Host "  2. Logs    " -NoNewline -ForegroundColor Yellow
    Write-Host " (View server logs - Ctrl+C to exit)"

    Write-Host "  3. Shell   " -NoNewline -ForegroundColor Magenta
    Write-Host " (Enter the container terminal)"

    Write-Host "  4. Stop    " -NoNewline -ForegroundColor Red
    Write-Host " (Shut down this dataset's container)"

    Write-Host "  5. Wipe DB " -NoNewline -ForegroundColor Red
    Write-Host " (RESET DB -> RESTART SERVER)"

    Write-Host "  6. Seed    " -NoNewline -ForegroundColor Green
    Write-Host " (Load data from scripts/ folder)"

    Write-Host ""
    Write-Host "  Q. Quit"
    Write-Host ""

    $Selection = Read-Host "Enter your choice"

    switch ($Selection) {
        "1" { $Run = "update" }
        "2" { $Run = "logs" }
        "3" { $Run = "shell" }
        "4" { $Run = "stop" }
        "5" { $Run = "wipe" }
        "6" { $Run = "seed" }
        "q" { exit }
        "Q" { exit }
        Default { Write-Host "Invalid selection." -ForegroundColor Red; exit }
    }
}

# --- 2. EXECUTION LOGIC ---
Write-Host ""
switch ($Run) {
    "update" {
        Write-Host "--- Rebuilding & Restarting '$Dataset'... ---" -ForegroundColor Cyan
        docker @Compose up -d --build
        $Port = (Select-String -Path $EnvFile -Pattern '^PORT=(.*)$').Matches.Groups[1].Value
        if (-not $Port) { $Port = "5000" }
        Write-Host "--- DONE. Dashboard is live at http://localhost:$Port ---" -ForegroundColor Green
    }
    "logs" {
        Write-Host "--- Tailing Logs for '$Dataset' (Press Ctrl+C to stop) ---" -ForegroundColor Cyan
        docker @Compose logs -f web
    }
    "shell" {
        Write-Host "--- Entering Container Shell (Type 'exit' to leave) ---" -ForegroundColor Cyan
        docker @Compose exec web /bin/bash
    }
    "stop" {
        Write-Host "--- Stopping '$Dataset'... ---" -ForegroundColor Yellow
        docker @Compose down
    }
    "wipe" {
        Assert-NotProtected
        Write-Host "WARNING: This DELETES every record in dataset '$Dataset'." -ForegroundColor Red
        $confirmation = Read-Host "Type the dataset name to confirm"
        if ($confirmation -eq $Dataset) {
            Write-Host "--- 1. Removing DB File... ---" -ForegroundColor Cyan
            docker @Compose exec web rm -f instance/estate.db

            # The migrations folder is tracked history, not scratch space:
            # 'flask db upgrade' rebuilds the schema from it. Deleting and
            # regenerating it, as this script used to, threw that history away.
            Write-Host "--- 2. Rebuilding Schema From Migrations... ---" -ForegroundColor Cyan
            docker @Compose exec web flask db upgrade

            Write-Host "--- 3. Restarting Web Server (Refreshing Connections)... ---" -ForegroundColor Cyan
            docker @Compose restart web

            Write-Host "--- DONE. Dataset '$Dataset' is clean and empty. ---" -ForegroundColor Green
        }
        else {
            Write-Host "Cancelled." -ForegroundColor Yellow
        }
    }
    "seed" {
        Assert-NotProtected
        if (-not $File) {
            $Default = "seed_example.py"
            Write-Host "Enter filename located in scripts/ (default: $Default)"
            $InputFile = Read-Host "> "
            if (-not $InputFile) { $File = $Default } else { $File = $InputFile }
        }

        Write-Host "--- Running scripts/$File against '$Dataset'... ---" -ForegroundColor Cyan
        docker @Compose exec web python scripts/$File
        Write-Host "--- DONE. ---" -ForegroundColor Green
    }
    Default {
        Write-Host "Unknown command: $Run" -ForegroundColor Red
    }
}
