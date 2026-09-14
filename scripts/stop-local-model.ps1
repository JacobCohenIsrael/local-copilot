$ErrorActionPreference = 'Stop'
$runtimeRoot = Join-Path (Split-Path -Parent $PSScriptRoot) '.runtime'
$pidPath = Join-Path $runtimeRoot 'ollama.pid'
if (-not (Test-Path -LiteralPath $pidPath)) { Write-Output 'No project service PID recorded.'; exit }
$serviceProcessId = [int](Get-Content -LiteralPath $pidPath -Raw).Trim()
$serviceProcess = Get-Process -Id $serviceProcessId -ErrorAction SilentlyContinue
if (-not $serviceProcess) { Write-Output 'Project service is already stopped.'; exit }
$expectedExecutable = [IO.Path]::GetFullPath((Join-Path $runtimeRoot 'ollama\ollama.exe'))
if ($serviceProcess.Path -ne $expectedExecutable) { throw 'Recorded PID belongs to a different executable; refusing to stop it.' }
Stop-Process -Id $serviceProcessId
Write-Output 'Stopped the project Ollama service.'
