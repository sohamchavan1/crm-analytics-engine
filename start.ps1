# CRM Intelligence Engine — Start both API and Frontend
# Run from the project root: .\start.ps1

Write-Host "Starting CRM Intelligence Engine..." -ForegroundColor Cyan
Write-Host ""

# Start FastAPI backend
Write-Host "[API] Starting FastAPI on http://localhost:8000" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; .\.venv\Scripts\Activate.ps1; uvicorn api.main:app --reload --port 8000"

# Wait a moment for backend to start
Start-Sleep -Seconds 2

# Start Next.js frontend
Write-Host "[UI]  Starting Next.js on http://localhost:3000" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; npm run dev"

Write-Host ""
Write-Host "Both services starting:" -ForegroundColor Cyan
Write-Host "  API:  http://localhost:8000/api/health" -ForegroundColor White
Write-Host "  UI:   http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C in each window to stop." -ForegroundColor DarkGray
