param(
    [string]$SourcePython = "python",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $Root ".runtime\premium"
$RuntimeSitePackages = Join-Path $RuntimeRoot "Lib\site-packages"
$Requirements = Join-Path $Root "requirements-premium.txt"

if ($Force -and (Test-Path -LiteralPath $RuntimeRoot)) {
    $ResolvedRoot = [System.IO.Path]::GetFullPath($Root)
    $ResolvedRuntime = [System.IO.Path]::GetFullPath($RuntimeRoot)
    if (!$ResolvedRuntime.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Diretorio de runtime fora do projeto: $ResolvedRuntime"
    }
    Remove-Item -LiteralPath $ResolvedRuntime -Recurse -Force
}

if (!(Test-Path -LiteralPath $Requirements)) {
    throw "Arquivo de requisitos premium nao encontrado: $Requirements"
}

$BasePython = & $SourcePython -c "import sys; print(sys.base_prefix)"
if (!$BasePython) {
    throw "Nao foi possivel localizar a instalacao base do Python."
}

Write-Host "Preparando runtime premium portatil em $RuntimeRoot" -ForegroundColor Cyan
New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
robocopy $BasePython $RuntimeRoot /E /XD (Join-Path $BasePython "Lib\site-packages") | Out-Null
$RoboExit = $LASTEXITCODE
if ($RoboExit -ge 8) {
    throw "Falha ao copiar o runtime Python base. robocopy exit code: $RoboExit"
}

New-Item -ItemType Directory -Path $RuntimeSitePackages -Force | Out-Null
& $SourcePython -m pip install --upgrade --target $RuntimeSitePackages --progress-bar off --no-compile -r $Requirements
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao instalar dependencias premium no runtime portatil."
}

$RuntimePython = Join-Path $RuntimeRoot "python.exe"
$env:PYTHONNOUSERSITE = "1"
& $RuntimePython -s -c "import demucs, torch, torchaudio, whisperx, whisper; print('Runtime premium pronto')"
if ($LASTEXITCODE -ne 0) {
    throw "O runtime premium foi montado, mas a validacao de imports falhou."
}

Write-Host "Runtime premium pronto: $RuntimePython" -ForegroundColor Green
