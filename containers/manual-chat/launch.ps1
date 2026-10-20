param([ValidateSet('review', 'run', 'status', 'stop')][string]$Action = 'review')
$ErrorActionPreference = 'Stop'
$ChatScript = Join-Path $PSScriptRoot 'chat.py'
$PythonCommand = Get-Command python -ErrorAction Stop
if ($Action -eq 'run') {
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
    if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'The existing CPU reader requires an administrator terminal. No automatic elevation or model start occurred.'
    }
}
& $PythonCommand.Source -B $ChatScript $Action
$ChatExitCode = $LASTEXITCODE
if ($Action -eq 'run') {
    $RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    $LiveRoot = Join-Path $RepoRoot '.runtime/strata-manual-chat-session'
    $ClaimFile = Join-Path $LiveRoot 'attempt.json'
    if (Test-Path -LiteralPath $ClaimFile) {
        $Claim = Get-Content -LiteralPath $ClaimFile -Raw | ConvertFrom-Json
        if ($Claim.sessionId -notmatch '^[0-9a-f]{32}$') { throw 'Invalid retained session identity' }
        $ReceiptFile = Join-Path $LiveRoot ('sessions/' + $Claim.sessionId + '/terminal-return-' + [guid]::NewGuid().ToString('N') + '.json')
        $Receipt = @{ controllerCommandReturned = $true; exitCode = $ChatExitCode; recordedAtUtc = [DateTime]::UtcNow.ToString('o'); terminalPid = $PID }
        $Receipt | ConvertTo-Json | Out-File -LiteralPath $ReceiptFile -Encoding utf8 -NoClobber
    }
}
exit $ChatExitCode
