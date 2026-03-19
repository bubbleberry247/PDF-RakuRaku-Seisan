# 請求書レビューヘルパー 起動スクリプト
# Usage: .\run.ps1 [-PaymentMonth "2026.3月分(2026.4末支払い)"]

param(
    [string]$PaymentMonth = ""
)

$toolsDir = Split-Path -Parent $PSScriptRoot
Set-Location $toolsDir

if ($PaymentMonth) {
    $env:REVIEW_HELPER_PAYMENT_MONTH = $PaymentMonth
}

Write-Host "=== 請求書レビューヘルパー ===" -ForegroundColor Cyan
Write-Host "URL: http://127.0.0.1:8021" -ForegroundColor Green
Write-Host "Ctrl+C で停止" -ForegroundColor Yellow
Write-Host ""

python -m review_helper
