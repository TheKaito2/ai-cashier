# Smoke test of the frozen build, run by CI on windows-latest after PyInstaller.
#   pwsh build/windows/smoke.ps1
# No camera, no display: --self-test scans the bundled demo frame; --server-only
# brings the dashboard up and a checkout goes through the REST door.
$ErrorActionPreference = "Stop"
$exe = Join-Path (Get-Location) "dist\AICashier\AI Cashier.exe"
$data = Join-Path $env:LOCALAPPDATA "AI Cashier"
if (-not (Test-Path $exe)) { throw "missing $exe" }

& $exe --self-test
if ($LASTEXITCODE -ne 0) { throw "self-test failed with exit code $LASTEXITCODE" }
$log = Get-Content (Join-Path $data "logs\app.log") -Raw
if ($log -notmatch "self-test ok") { throw "no 'self-test ok' line in the log:`n$log" }
Write-Host (($log -split "`n" | Select-String "self-test ok" | Select-Object -Last 1).Line)

$p = Start-Process -FilePath $exe -ArgumentList "--server-only" -PassThru
try {
    $ok = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $r = Invoke-WebRequest "http://127.0.0.1:8000/api/system-status" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $ok = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    if (-not $ok) { throw "the dashboard did not answer on 127.0.0.1:8000" }
    Write-Host "system-status 200: $($r.Content)"
    foreach ($page in "/", "/inventory", "/admin") {
        $s = (Invoke-WebRequest "http://127.0.0.1:8000$page" -UseBasicParsing).StatusCode
        if ($s -ne 200) { throw "$page returned $s" }
    }
    $products = Invoke-RestMethod "http://127.0.0.1:8000/api/products"
    $body = @{ items = @(@{ product_id = $products[0].id; quantity = 1 }) } | ConvertTo-Json -Depth 4
    $pay = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/checkout" -ContentType "application/json" -Body $body
    Write-Host "checkout 200: payment $($pay.payment_id) total $($pay.total) payable $($pay.payable)"
} finally {
    Stop-Process -Id $p.Id -Force
}
