param(
    [switch]$Clean,
    [switch]$SkipInstall,
    [switch]$PreparePremiumRuntime,
    [switch]$BundlePremiumRuntime
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$BuildLog = Join-Path $LogDir "build_standalone_full.log"
$PremiumRuntime = Join-Path $Root ".runtime\premium"

Write-Host "AudioAgent Desktop Full - build standalone" -ForegroundColor Cyan
Write-Host "Projeto: $Root"
Write-Host "Log: $BuildLog"

if ($Clean) {
    Write-Host "Limpando build/dist anteriores..."
    Remove-Item -LiteralPath (Join-Path $Root "build") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $Root "dist") -Recurse -Force -ErrorAction SilentlyContinue
}

if (!$SkipInstall) {
    python -m pip install --upgrade pip
    python -m pip install -r requirements-standalone-shell.txt
    python -m pip install pyinstaller
}

if ($PreparePremiumRuntime) {
    & (Join-Path $PSScriptRoot "setup_premium_runtime.ps1")
}

python -m compileall app.py services core desktop_launcher.py

$PreviousPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
python -m PyInstaller --clean --noconfirm AudioAgentDesktop.spec 2>&1 | Tee-Object -FilePath $BuildLog
$PyInstallerExit = $LASTEXITCODE
$ErrorActionPreference = $PreviousPreference
if ($PyInstallerExit -ne 0) {
    throw "PyInstaller falhou com exit code $PyInstallerExit. Veja o log: $BuildLog"
}

$DistDir = Join-Path $Root "dist\AudioAgentDesktop"
$Exe = Join-Path $DistDir "AudioAgentDesktop.exe"
if (!(Test-Path -LiteralPath $Exe)) {
    throw "Executavel nao encontrado em $Exe"
}

if ($BundlePremiumRuntime) {
    & (Join-Path $PSScriptRoot "bundle_premium_runtime.ps1") -DistDir $DistDir
}

Write-Host "Build concluido:" -ForegroundColor Green
Write-Host $Exe
Write-Host "Dados locais do app ficarao em: $env:LOCALAPPDATA\AudioAgent"
if ($BundlePremiumRuntime) {
    Write-Host "Runtime premium incorporado em: $DistDir\runtime\premium" -ForegroundColor Green
} else {
    Write-Host "Runtime premium externo: configure AUDIOAGENT_PREMIUM_PYTHON ou execute em um computador com Python premium instalado." -ForegroundColor Yellow
}
