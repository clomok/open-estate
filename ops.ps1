<#
.SYNOPSIS
    Operations Manager for Open Estate Dashboard.
.EXAMPLE
    .\ops.ps1               (Launches Interactive Menu)
    .\ops.ps1 -Run update   (Bypasses menu, runs Update immediately)
#>

param (
    [string]$Run = ""
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
    
    Write-Host ""
    Write-Host "  Q. Quit"
    Write-Host ""
    
    $Selection = Read-Host "Enter your choice"

    # Map the menu numbers to command keywords
    switch ($Selection) {
        "1" { $Run = "update" }
        "2" { $Run = "logs" }
        "3" { $Run = "shell" }
        "4" { $Run = "stop" }
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
        Write-Host "--- DONE. Dashboard is live at http://localhost:5070 ---" -ForegroundColor Green
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
    Default {
        Write-Host "Unknown command: $Run" -ForegroundColor Red
        Write-Host "Available commands: update, logs, shell, stop"
    }
}