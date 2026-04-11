param(
  [int]$InitialPort = 18080
)

$rootDir = 'C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\docs\assets\doboku-14w'
$relativePath = 'figure-pages/figure-pages-viewer-by-map.html'
$targetFile = Join-Path $rootDir $relativePath

if (-not (Test-Path $targetFile)) {
  throw "Target file not found: $targetFile"
}

function Test-ViewerServer([int]$targetPort) {
  try {
    $url = "http://127.0.0.1:$targetPort/$relativePath"
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1
    return $response.StatusCode -eq 200
  }
  catch {
    return $false
  }
}

$port = $InitialPort
$found = $false
for ($i = 0; $i -lt 20; $i++) {
  if (Test-ViewerServer -targetPort $port) {
    $found = $true
    break
  }

  if ($i -eq 19) {
    break
  }
  $port++
}

if (-not $found) {
  $command = @"
Set-Location '$rootDir'
python -m http.server $port --bind 127.0.0.1
"@

  Start-Process -WindowStyle Hidden -FilePath powershell -ArgumentList '-NoProfile', '-NoLogo', '-Command', $command
  Start-Sleep -Milliseconds 1200
}

$targetUrl = "http://127.0.0.1:$port/$relativePath"
Write-Output "Figure viewer URL: $targetUrl"
Start-Process $targetUrl

