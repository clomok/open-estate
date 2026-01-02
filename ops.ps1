<#
.SYNOPSIS
    Operations Manager for Open Estate Dashboard.
.EXAMPLE
    .\ops.ps1                           (Interactive Menu)
    .\ops.ps1 -Run wipe                 (Wipe & Reset DB)
    .\ops.ps1 -Run seed -File seed.py   (Run specific seed script)
#>

param (
    [string]$Run = "",
    [string]$File = ""
)

# --- 1. INTERACTIVE MENU MODE ---
if (-not $Run) {
    Clear-Host
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "      OPEN ESTATE - OPS MANAGER       " -ForegroundColor White
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  1. Update  " -NoNewline -ForegroundColor Green
    Write-Host " (Rebuild container & restart)"
    
    Write-Host "  2. Logs    " -NoNewline -ForegroundColor Yellow
    Write-Host " (View server logs - Ctrl+C to exit)"
    
    Write-Host "  3. Shell   " -NoNewline -ForegroundColor Magenta
    Write-Host " (Enter the container terminal)"
    
    Write-Host "  4. Stop    " -NoNewline -ForegroundColor Red
    Write-Host " (Shut down all containers)"

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
        Write-Host "--- Rebuilding & Restarting... ---" -ForegroundColor Cyan
        docker-compose up -d --build
        Write-Host "--- DONE. Dashboard is live at http://localhost:5000 ---" -ForegroundColor Green
    }
    "logs" {
        Write-Host "--- Tailing Logs (Press Ctrl+C to stop) ---" -ForegroundColor Cyan
        docker-compose logs -f web
    }
    "shell" {
        Write-Host "--- Entering Container Shell (Type 'exit' to leave) ---" -ForegroundColor Cyan
        docker-compose exec web /bin/bash
    }
    "stop" {
        Write-Host "--- Stopping Containers... ---" -ForegroundColor Yellow
        docker-compose down
    }
    "wipe" {
        Write-Host "⚠️  WARNING: This will DELETE all data in instance/estate.db" -ForegroundColor Red
        $confirmation = Read-Host "Are you sure? (y/n)"
        if ($confirmation -eq 'y') {
            Write-Host "--- 1. Removing DB File... ---" -ForegroundColor Cyan
            docker-compose exec web rm -f instance/estate.db
            
            Write-Host "--- 2. Removing Migrations Folder... ---" -ForegroundColor Cyan
            docker-compose exec web rm -rf migrations

            Write-Host "--- 3. Initializing DB... ---" -ForegroundColor Cyan
            docker-compose exec web flask db init
            docker-compose exec web flask db migrate -m "Reset by Ops Manager"
            docker-compose exec web flask db upgrade
            
            Write-Host "--- 4. Restarting Web Server (Refreshing Connections)... ---" -ForegroundColor Cyan
            docker-compose restart web
            
            Write-Host "--- DONE. Database is clean and empty. ---" -ForegroundColor Green
        }
        else {
            Write-Host "Cancelled." -ForegroundColor Yellow
        }
    }
    "seed" {
        if (-not $File) {
            $Default = "seed_example.py"
            Write-Host "Enter filename located in scripts/ (default: $Default)"
            $InputFile = Read-Host "> "
            if (-not $InputFile) { $File = $Default } else { $File = $InputFile }
        }
        
        Write-Host "--- Running scripts/$File ... ---" -ForegroundColor Cyan
        docker-compose exec web python scripts/$File
        Write-Host "--- DONE. ---" -ForegroundColor Green
    }
    Default {
        Write-Host "Unknown command: $Run" -ForegroundColor Red
    }
}