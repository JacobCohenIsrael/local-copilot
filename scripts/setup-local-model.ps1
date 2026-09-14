param([string]$Model = 'qwen2.5-coder:7b')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot '.runtime'
$ollamaRoot = Join-Path $runtimeRoot 'ollama'
$archivePath = Join-Path $runtimeRoot 'ollama-windows-amd64.zip'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$executable = Join-Path $ollamaRoot 'ollama.exe'
if (-not (Test-Path -LiteralPath $executable)) {
    $release = Invoke-RestMethod 'https://api.github.com/repos/ollama/ollama/releases/tags/v0.34.0'
    $asset = $release.assets | Where-Object name -eq 'ollama-windows-amd64.zip'
    if (-not $asset -or -not $asset.digest.StartsWith('sha256:')) { throw 'Release asset or checksum is missing.' }
    if (-not (Test-Path -LiteralPath $archivePath)) {
        Write-Output 'Downloading portable Ollama (approximately 1.47 GB)...'
        Invoke-WebRequest $asset.browser_download_url -OutFile $archivePath
    }
    $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $asset.digest.Substring(7)) { throw 'Ollama archive checksum mismatch. Remove the archive and retry.' }
    Write-Output 'Extracting verified Ollama archive...'
    Expand-Archive -LiteralPath $archivePath -DestinationPath $ollamaRoot -Force
}
$env:OLLAMA_HOST = '127.0.0.1:11435'
$env:OLLAMA_MODELS = Join-Path $runtimeRoot 'models'
$env:OLLAMA_NO_CLOUD = '1'
try { $null = Invoke-RestMethod 'http://127.0.0.1:11435/api/tags' -TimeoutSec 2 }
catch {
    $process = Start-Process -FilePath $executable -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'ollama.stdout.log') -RedirectStandardError (Join-Path $runtimeRoot 'ollama.stderr.log')
    $process.Id | Set-Content (Join-Path $runtimeRoot 'ollama.pid')
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Seconds 1
        try { $null = Invoke-RestMethod 'http://127.0.0.1:11435/api/tags' -TimeoutSec 2; $ready = $true; break } catch {}
    }
    if (-not $ready) { throw 'Ollama did not start. Inspect .runtime/ollama.stderr.log.' }
}
Write-Output "Preparing local model $Model..."
& $executable pull $Model
if ($LASTEXITCODE -ne 0) { throw 'Model download failed.' }
Write-Output "Ready: npm start -- doctor --host http://127.0.0.1:11435 --model $Model"
