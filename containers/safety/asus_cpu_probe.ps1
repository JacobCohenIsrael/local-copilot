# Reviewable, fixed read-only probe. No elevation, driver installation, or writes to device settings.
# This script is not run automatically. It may be denied by Windows access controls.
$ErrorActionPreference = 'Stop'
$result = [ordered]@{
    operation = 'DSTS'
    deviceId = '0x00120094'
    mode = 'read-only-candidate'
    settingsChanged = $false
    verifiedSafetySensor = $false
    stage = 'computer-identity'
    isAdministrator = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
try {
    $computer = Get-CimInstance Win32_ComputerSystem -OperationTimeoutSec 3
    if ($computer.Manufacturer -ne 'ASUSTeK COMPUTER INC.' -or $computer.Model -ne 'ROG Strix G733CX_G733CX') {
        throw 'This fixed probe is scoped to the inspected laptop model'
    }
    $result.stage = 'asus-wmi-instance'
    $sensor = @(Get-CimInstance -Namespace root/wmi -ClassName AsusAtkWmi_WMNB -OperationTimeoutSec 3)
    if ($sensor.Count -ne 1) { throw 'Expected exactly one ASUS WMI instance' }
    # DSTS = device status. DEVS and all other vendor methods are intentionally absent.
    $result.stage = 'cpu-device-status'
    $status = Invoke-CimMethod -InputObject $sensor[0] -MethodName DSTS `
        -Arguments @{ Device_ID=[uint32]0x00120094 } -OperationTimeoutSec 3
    $result.returnValue = $status.ReturnValue
    $result.rawDeviceStatus = $status.device_status
    $result.present = (([uint32]$status.device_status -band 0x10000) -ne 0)
    $candidate = [int64]$status.device_status - 65536
    $result.temperatureCandidateC = $(if ($result.present -and $candidate -gt 0 -and $candidate -le 125) { $candidate } else { $null })
    $result.stage = 'complete'
} catch { $result.error = $_.Exception.Message }
$result | ConvertTo-Json -Depth 4
