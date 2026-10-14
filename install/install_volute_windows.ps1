# Installs or updates VOLUTE on Windows, in a folder of its own holding
# everything it needs: Miniforge, its Python environment, SAM2-Plus, the
# models and VOLUTE itself. Nothing outside that folder is changed, apart from
# the VOLUTE shortcut on the Desktop.
#
# Paste into PowerShell, or into a Command Prompt:
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_windows.ps1 | iex"
#
# The folder is %USERPROFILE%\VOLUTE, or C:\VOLUTE when the user folder's path
# holds spaces or non-ASCII characters, which conda does not handle reliably.
# This script installs Miniforge into it, then hands over to
# volute_installer.py, run with Miniforge's own Python.
#
# Environment variables:
#   VOLUTE_PREFIX            installation folder
#   VOLUTE_INSTALLER_ARGS    options passed on to volute_installer.py
#   VOLUTE_INSTALLER_SOURCE  local volute_installer.py to run instead of the
#                            published one, for testing

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is far slower with it
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$RawBase = 'https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install'

function Stop-Installer($Message) {
    Write-Host ''
    Write-Host "Error: $Message" -ForegroundColor Red
    Write-Host ''
    Read-Host 'Press Enter to close'
    # Run through "irm | iex", exit would close the PowerShell window itself
    throw $Message
}

Write-Host '======================================================================'
Write-Host 'VOLUTE installer (Windows)'
Write-Host '======================================================================'
Write-Host ''

if (-not [Environment]::Is64BitOperatingSystem) {
    Stop-Installer 'VOLUTE needs a 64-bit Windows.'
}

if ($env:VOLUTE_PREFIX) {
    $Prefix = $env:VOLUTE_PREFIX
} elseif ($env:USERPROFILE -match '^[\x21-\x7E]+$') {
    $Prefix = Join-Path $env:USERPROFILE 'VOLUTE'
} else {
    $Prefix = 'C:\VOLUTE'
    Write-Host "Your user folder's path contains spaces or accented characters,"
    Write-Host "which the Python tools VOLUTE relies on handle poorly: installing"
    Write-Host "into $Prefix instead."
    Write-Host ''
}
if ($Prefix -notmatch '^[\x21-\x7E]+$') {
    Stop-Installer "the installation folder must not contain spaces or accented characters: $Prefix"
}
New-Item -ItemType Directory -Force -Path $Prefix | Out-Null

$Miniforge = Join-Path $Prefix 'miniforge3'
$MiniforgePython = Join-Path $Miniforge 'python.exe'

if (-not (Test-Path $MiniforgePython)) {
    Write-Host 'Installing Miniforge, the Python distribution VOLUTE runs on, into'
    Write-Host "  $Miniforge"
    Write-Host 'This takes a few minutes.'
    $Installer = Join-Path $env:TEMP 'Miniforge3-Windows-x86_64.exe'
    Invoke-WebRequest -UseBasicParsing -OutFile $Installer `
        -Uri 'https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe'
    # Silent, for this user only, without touching PATH, the registered Python,
    # the Start menu or the list of installed applications, whose uninstall
    # entry would outlive the folder; /D must come last and stay unquoted
    $Process = Start-Process -FilePath $Installer -Wait -PassThru -ArgumentList `
        '/InstallationType=JustMe', '/RegisterPython=0', '/AddToPath=0', '/NoShortcuts=1', '/NoRegistry=1', '/S', "/D=$Miniforge"
    Remove-Item $Installer -ErrorAction SilentlyContinue
    if ($Process.ExitCode -ne 0 -or -not (Test-Path $MiniforgePython)) {
        Stop-Installer "Miniforge could not be installed (exit code $($Process.ExitCode))."
    }
    # The Miniforge installer lists its folder in ~\.conda\environments.txt,
    # whatever CONDA_REGISTER_ENVS says: that line is taken out again, and the
    # file and its folder too when nothing else is left in them. Read and
    # written as UTF-8 without BOM, as conda does.
    $CondaDir = Join-Path $env:USERPROFILE '.conda'
    $EnvList = Join-Path $CondaDir 'environments.txt'
    if (Test-Path $EnvList) {
        $Kept = @([IO.File]::ReadAllLines($EnvList) |
            Where-Object { $_.Trim() -and $_.Trim().TrimEnd('\') -ne $Miniforge.TrimEnd('\') })
        if ($Kept.Count) {
            [IO.File]::WriteAllLines($EnvList, [string[]]$Kept)
        } else {
            Remove-Item $EnvList
        }
        if (-not (Get-ChildItem $CondaDir -Force)) { Remove-Item $CondaDir }
    }
    Write-Host ''
} else {
    Write-Host "Miniforge already installed in $Miniforge"
}

if ($env:VOLUTE_INSTALLER_SOURCE) {
    $Core = $env:VOLUTE_INSTALLER_SOURCE
} else {
    $Core = Join-Path $Prefix 'volute_installer.py'
    Invoke-WebRequest -UseBasicParsing -OutFile $Core -Uri "$RawBase/volute_installer.py"
}

$Arguments = @($Core, '--prefix', $Prefix, '--miniforge', $Miniforge)
if ($env:VOLUTE_INSTALLER_ARGS) {
    $Arguments += $env:VOLUTE_INSTALLER_ARGS -split '\s+'
}
& $MiniforgePython @Arguments
$Status = $LASTEXITCODE

Write-Host ''
Read-Host 'Press Enter to close'
if ($Status -ne 0) {
    throw 'The installation did not complete.'
}
