param(
    [string]$DistDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PremiumRuntime = Join-Path $Root ".runtime\premium"
if (!$DistDir) {
    $DistDir = Join-Path $Root "dist\AudioAgentDesktop"
}
$TargetRuntime = Join-Path $DistDir "runtime\premium"

if (!(Test-Path -LiteralPath (Join-Path $PremiumRuntime "python.exe"))) {
    throw "Runtime premium nao preparado. Execute scripts\setup_premium_runtime.ps1 primeiro."
}
if (!(Test-Path -LiteralPath (Join-Path $DistDir "AudioAgentDesktop.exe"))) {
    throw "Executavel standalone nao encontrado em $DistDir"
}

Write-Host "Anexando runtime premium em $TargetRuntime" -ForegroundColor Cyan
New-Item -ItemType Directory -Path $TargetRuntime -Force | Out-Null
robocopy $PremiumRuntime $TargetRuntime /E /R:2 /W:2 | Out-Null
$RoboExit = $LASTEXITCODE
if ($RoboExit -ge 8) {
    throw "Falha ao copiar runtime premium. robocopy exit code: $RoboExit"
}

$RuntimePython = Join-Path $TargetRuntime "python.exe"
$env:PYTHONNOUSERSITE = "1"
& $RuntimePython -s -c "import demucs, torch, torchaudio, whisperx, whisper; print('Runtime premium incorporado e validado')"
if ($LASTEXITCODE -ne 0) {
    throw "Runtime copiado, mas a validacao de imports falhou."
}

Write-Host "Runtime premium anexado com sucesso." -ForegroundColor Green
