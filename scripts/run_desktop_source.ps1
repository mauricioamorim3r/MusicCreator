$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:AUDIOAGENT_DESKTOP_MODE = "1"
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"

python desktop_launcher.py
