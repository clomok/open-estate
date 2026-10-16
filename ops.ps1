<#
.SYNOPSIS
    Operations Manager for Open Estate Dashboard.
.DESCRIPTION
    One stack serves every estate (see datasets/README.md). Starting, stopping
    and logs act on the stack; Seed and Wipe act on ONE estate, which you must
    name - there is no default, and a protected estate is refused by the
    scripts themselves.
.EXAMPLE
    .\ops.ps1                                    (Interactive Menu)
    .\ops.ps1 -Run update                        (Rebuild & restart)
    .\ops.ps1 -Run wipe -Estate demo             (Empty one estate)
    .\ops.ps1 -Run seed -Estate demo -File seed_example.py
    .\ops.ps1 -Run adopt -Estate family          (Move an old dataset in)
#>

param (
    [string]$Estate = "",
    [string]$Run = "",
    [string]$File = ""
)

$SiteEnv = "datasets/site.env"
if ($Run -ne "adopt" -and -not (Test-Path $SiteEnv)) {
    Write-Host "No $SiteEnv. Copy datasets/site.env.example and fill it in." -ForegroundColor Red
    Write-Host "Upgrading from the one-container-per-dataset layout? Stop the old stack, then"
    Write-Host "run '.\ops.ps1 -Run adopt -Estate <old dataset name>' once per dataset."
    exit 1
}

# Compose reads this one file for both interpolation and the container's env.
$Compose = @("compose", "--env-file", $SiteEnv)

function Require-Estate {
    if (-not $script:Estate) {
        Write-Host ""
        Write-Host "Which estate?" -ForegroundColor Cyan
        python scripts/estate_admin.py list
        Write-Host ""
        $script:Estate = Read-Host "Estate name"
    }
    if (-not $script:Estate) { Write-Host "Cancelled." -ForegroundColor Yellow; exit 1 }
}

# --- 1. INTERACTIVE MENU MODE ---
if (-not $Run) {
    Clear-Host
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "      OPEN ESTATE - OPS MANAGER       " -ForegroundColor White
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "  Estates:" -ForegroundColor Gray
    python scripts/estate_admin.py list
    Write-Host ""
    Write-Host "  1. Update  " -NoNewline -ForegroundColor Green
    Write-Host " (Rebuild container & restart)"

    Write-Host "  2. Logs    " -NoNewline -ForegroundColor Yellow
    Write-Host " (View server logs - Ctrl+C to exit)"

    Write-Host "  3. Shell   " -NoNewline -ForegroundColor Magenta
    Write-Host " (Enter the container terminal)"

    Write-Host "  4. Stop    " -NoNewline -ForegroundColor Red
    Write-Host " (Shut down the stack)"

    Write-Host "  5. Wipe    " -NoNewline -ForegroundColor Red
    Write-Host " (EMPTY one demo estate - not needed for schema changes)"

    Write-Host "  6. Seed    " -NoNewline -ForegroundColor Green
    Write-Host " (Load data from scripts/ folder into one estate)"

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
        Write-Host "--- Rebuilding & Restarting... ---" -ForegroundColor Cyan
        docker @Compose up -d --build
        $Port = (Select-String -Path $SiteEnv -Pattern '^PORT=(.*)$').Matches.Groups[1].Value
        if (-not $Port) { $Port = "5000" }
        Write-Host "--- DONE. Dashboard is live at http://localhost:$Port ---" -ForegroundColor Green
    }
    "logs" {
        Write-Host "--- Tailing Logs (Press Ctrl+C to stop) ---" -ForegroundColor Cyan
        docker @Compose logs -f web
    }
    "shell" {
        Write-Host "--- Entering Container Shell (Type 'exit' to leave) ---" -ForegroundColor Cyan
        docker @Compose exec web /bin/bash
    }
    "stop" {
        Write-Host "--- Stopping... ---" -ForegroundColor Yellow
        docker @Compose down
    }
    "adopt" {
        Require-Estate
        python scripts/estate_admin.py adopt $Estate
    }
    "wipe" {
        Require-Estate
        # The script refuses a protected estate, asks for the typed name, and
        # moves the old database to that estate's backups/ folder.
        docker @Compose exec web python scripts/estate_admin.py wipe $Estate
        if ($LASTEXITCODE -eq 0) {
            Write-Host "--- Restarting Web Server (Refreshing Connections)... ---" -ForegroundColor Cyan
            docker @Compose restart web
            Write-Host "    (A schema change never needs a wipe: restarting the container" -ForegroundColor DarkGray
            Write-Host "     runs scripts/upgrade_db.py, which migrates every estate in place.)" -ForegroundColor DarkGray
        }
    }
    "seed" {
        Require-Estate
        if (-not $File) {
            $Default = "seed_example.py"
            Write-Host "Enter filename located in scripts/ (default: $Default)"
            $InputFile = Read-Host "> "
            if (-not $InputFile) { $File = $Default } else { $File = $InputFile }
        }

        Write-Host "--- Running scripts/$File against estate '$Estate'... ---" -ForegroundColor Cyan
        docker @Compose exec web python scripts/$File --estate $Estate
        Write-Host "--- DONE. ---" -ForegroundColor Green
    }
    Default {
        Write-Host "Unknown command: $Run" -ForegroundColor Red
    }
}
