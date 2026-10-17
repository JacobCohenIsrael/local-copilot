# Fixed bounded ASUS reader. No self-elevation, device writes, arbitrary endpoint or workload.
param(
    [string]$SessionDirectory,
    [ValidateRange(1,1920)][int]$Samples = 3,
    [switch]$Describe
)
$ErrorActionPreference = 'Stop'
$maxDurationSeconds = 1920
$sampleIntervalSeconds = 1
if ($Describe) {
    [ordered]@{ version=1; maxDurationSeconds=$maxDurationSeconds; maxSamples=1920;
        requestedSamples=$Samples; defaultSamples=3; sampleIntervalSeconds=$sampleIntervalSeconds;
        frameBudget=2048; sensorAccessed=$false; workloadStarted=$false;
        validatedCpuSensor=$false; longRunValidated=$false } | ConvertTo-Json -Compress
    return
}
if (-not $SessionDirectory) { throw 'SessionDirectory is required unless describing the contract' }
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
$sessionClock = [Diagnostics.Stopwatch]::StartNew()
try {
    if (-not $isAdmin) { throw 'Administrator access required for the inspected ASUS source' }
    $computer = Get-CimInstance Win32_ComputerSystem -OperationTimeoutSec 2
    if ($computer.Manufacturer -ne 'ASUSTeK COMPUTER INC.' -or $computer.Model -ne 'ROG Strix G733CX_G733CX') { throw 'Unexpected laptop model' }
    $instances = @(Get-CimInstance -Namespace root/wmi -ClassName AsusAtkWmi_WMNB -OperationTimeoutSec 2)
    if ($instances.Count -ne 1) { throw 'Unexpected ASUS instance count' }
    $sensor = $instances[0]
} catch { $initialError = $_.Exception.Message }
$samplingStarted = $sessionClock.Elapsed.TotalSeconds
$lastSampleSlot = $samplingStarted + ($Samples - 1) * $sampleIntervalSeconds
for ($sequence=1; $sequence -le $Samples; $sequence++) {
    # Fixed monotonic slots avoid accumulating query duration on every interval.
    $due = $samplingStarted + ($sequence - 1) * $sampleIntervalSeconds
    $waitMs = [math]::Ceiling(1000 * ($due - $sessionClock.Elapsed.TotalSeconds))
    if ($waitMs -gt 0) { Start-Sleep -Milliseconds $waitMs }
    if ($sessionClock.Elapsed.TotalSeconds -ge $maxDurationSeconds) { break }
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
    # Declared remaining coverage is not a liveness guarantee. Default three-sample
    # probes must never masquerade as a full-build monitoring session.
    $sample.readerRemainingSeconds = [math]::Max(0,
        [math]::Min($maxDurationSeconds, $lastSampleSlot) - $sessionClock.Elapsed.TotalSeconds)
    $temporary = Join-Path $directory ('sample-' + $sequence + '.tmp')
    $json = $sample | ConvertTo-Json -Depth 4 -Compress
    [IO.File]::WriteAllText($temporary, $json)
    $target = Join-Path $directory ('sample-{0:D8}.json' -f $sequence)
    [IO.File]::Move($temporary,$target) # Immutable frames avoid Windows replace/read sharing races.
    Add-Content -LiteralPath (Join-Path $directory 'samples.jsonl') -Value $json -Encoding UTF8
    if ($sample.error -or $sample.querySeconds -gt 1) { break }
}
