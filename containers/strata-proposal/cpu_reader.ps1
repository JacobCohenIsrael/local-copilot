# Fixed bounded ASUS reader. No self-elevation, device writes, arbitrary endpoint or workload.
param(
    [Parameter(Mandatory=$true)][string]$SessionDirectory,
    [ValidateRange(1,1800)][int]$Samples = 3
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../.runtime/compiler-guard'))
$directory = [IO.Path]::GetFullPath($SessionDirectory)
if ([IO.Path]::GetDirectoryName($directory) -ne $root -or [IO.Path]::GetFileName($directory) -notmatch '^[a-f0-9]{32}$') { throw 'Invalid reader session' }
$cursor = $directory
while ($cursor) {
    if (Test-Path -LiteralPath $cursor) {
        if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reader path must not contain reparse points' }
    }
    $parent = [IO.Path]::GetDirectoryName($cursor)
    if ($parent -eq $cursor) { break }
    $cursor = $parent
}
if (-not (Test-Path -LiteralPath $directory -PathType Container)) { throw 'Session must already exist' }
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$sensor = $null
$initialError = $null
try {
    if (-not $isAdmin) { throw 'Administrator access required for the inspected ASUS source' }
    $computer = Get-CimInstance Win32_ComputerSystem -OperationTimeoutSec 2
    if ($computer.Manufacturer -ne 'ASUSTeK COMPUTER INC.' -or $computer.Model -ne 'ROG Strix G733CX_G733CX') { throw 'Unexpected laptop model' }
    $instances = @(Get-CimInstance -Namespace root/wmi -ClassName AsusAtkWmi_WMNB -OperationTimeoutSec 2)
    if ($instances.Count -ne 1) { throw 'Unexpected ASUS instance count' }
    $sensor = $instances[0]
} catch { $initialError = $_.Exception.Message }
$sessionClock = [Diagnostics.Stopwatch]::StartNew()
for ($sequence=1; $sequence -le $Samples -and $sessionClock.Elapsed.TotalSeconds -lt 1800; $sequence++) {
    $clock = [Diagnostics.Stopwatch]::StartNew()
    $sample = [ordered]@{ version=1; sequence=$sequence; synthetic=$false; cpuTemperatureC=$null; cpuThermalThrottling=$null; validatedCpuSensor=$false; source='ASUS DSTS 0x00120094'; error=$null }
    try {
        if ($initialError) { throw $initialError }
        $status = Invoke-CimMethod -InputObject $sensor -MethodName DSTS -Arguments @{ Device_ID=[uint32]0x00120094 } -OperationTimeoutSec 2
        if ($status.ReturnValue -ne $true) { throw 'ASUS status read failed' }
        $raw = [uint32]$status.device_status
        $temp = [int64]$raw - 65536
        if (($raw -band 0x10000) -eq 0 -or $temp -le 0 -or $temp -gt 125) { throw 'Unsupported or invalid CPU temperature' }
        $sample.cpuTemperatureC = $temp
    } catch { $sample.error = $_.Exception.Message }
    $sample.querySeconds = $clock.Elapsed.TotalSeconds
    $sample.recordedAtUnix = ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0)
    $temporary = Join-Path $directory ('sample-' + $sequence + '.tmp')
    $json = $sample | ConvertTo-Json -Depth 4 -Compress
    [IO.File]::WriteAllText($temporary, $json)
    $target = Join-Path $directory ('sample-{0:D8}.json' -f $sequence)
    [IO.File]::Move($temporary,$target) # Immutable frames avoid Windows replace/read sharing races.
    Add-Content -LiteralPath (Join-Path $directory 'samples.jsonl') -Value $json -Encoding UTF8
    if ($initialError) { break }
    if ($sequence -lt $Samples) { Start-Sleep -Milliseconds 1000 }
}
