param(
    [Parameter(Mandatory = $true)][string]$IdePath
)
$ErrorActionPreference = 'Stop'
$pluginRoot = $PSScriptRoot
$sdk = (Resolve-Path -LiteralPath $IdePath).Path
$output = Join-Path $pluginRoot 'build'
$classes = Join-Path $output 'classes'
$package = Join-Path $output 'package/local-copilot/lib'
New-Item -ItemType Directory -Force -Path $classes, $package | Out-Null
$javac = Join-Path $sdk 'jbr/bin/javac.exe'
$classpath = (Join-Path $sdk 'lib/*') + ';' + (Join-Path $sdk 'lib/modules/*')
$source = @(Get-ChildItem -LiteralPath (Join-Path $pluginRoot 'src/main/java') -Filter '*.java' -Recurse -File | Select-Object -ExpandProperty FullName)
& $javac --release 21 -encoding UTF-8 -cp $classpath -d $classes $source
if ($LASTEXITCODE -ne 0) { throw 'Plugin compilation failed.' }
Copy-Item -Path (Join-Path $pluginRoot 'src/main/resources/*') -Destination $classes -Recurse -Force
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
function Write-PortableZip([string]$SourceDirectory, [string]$ArchivePath) {
    if (Test-Path -LiteralPath $ArchivePath) { Remove-Item -LiteralPath $ArchivePath }
    $archive = [System.IO.Compression.ZipFile]::Open($ArchivePath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $basePath = (Resolve-Path -LiteralPath $SourceDirectory).Path.TrimEnd('\') + '\'
        foreach ($item in Get-ChildItem -LiteralPath $SourceDirectory -File -Recurse) {
            $entryName = $item.FullName.Substring($basePath.Length).Replace('\', '/')
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $item.FullName, $entryName) | Out-Null
        }
    } finally { $archive.Dispose() }
}
$pluginJar = Join-Path $package 'local-copilot.jar'
Write-PortableZip $classes $pluginJar
$metadata = [xml](Get-Content -LiteralPath (Join-Path $pluginRoot 'src/main/resources/META-INF/plugin.xml') -Raw)
$zip = Join-Path $output ('local-copilot-' + $metadata.'idea-plugin'.version + '.zip')
Write-PortableZip (Join-Path $output 'package') $zip
Write-Output "Plugin ZIP: $zip"
