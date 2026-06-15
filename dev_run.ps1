# Stop any process already listening on port 5000, then start Flask once.
$listeners = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
foreach ($conn in $listeners) {
    Write-Host "Stopping PID $($conn.OwningProcess) on port 5000..."
    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1
Set-Location $PSScriptRoot
& .\akellodashboard\Scripts\flask.exe run --host 127.0.0.1 --port 5000
