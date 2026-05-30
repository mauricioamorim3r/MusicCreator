param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$BuildLog = Join-Path $LogDir "build_standalone_full.log"

Write-Host "AudioAgent Desktop Full - build standalone" -ForegroundColor Cyan
Write-Host "Projeto: $Root"
Write-Host "Log: $BuildLog"

if ($Clean) {
    Write-Host "Limpando build/dist anteriores..."
    Remove-Item -LiteralPath (Join-Path $Root "build") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $Root "dist") -Recurse -Force -ErrorAction SilentlyContinue
}

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller imageio-ffmpeg openai-whisper

python -m compileall app.py services core desktop_launcher.py

$PreviousPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
python -m PyInstaller --clean --noconfirm AudioAgentDesktop.spec 2>&1 | Tee-Object -FilePath $BuildLog
$PyInstallerExit = $LASTEXITCODE
$ErrorActionPreference = $PreviousPreference
if ($PyInstallerExit -ne 0) {
    throw "PyInstaller falhou com exit code $PyInstallerExit. Veja o log: $BuildLog"
}

$Exe = Join-Path $Root "dist\AudioAgentDesktop\AudioAgentDesktop.exe"
if (!(Test-Path $Exe)) {
    throw "Executavel nao encontrado em $Exe"
}

Write-Host "Build concluido:" -ForegroundColor Green
Write-Host $Exe
Write-Host "Dados locais do app ficarao em: $env:LOCALAPPDATA\AudioAgent"
