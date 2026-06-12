$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$entryPoint = "difficulty_stamina_game.py"
$exeName = "DifficultyStaminaMaze"
$pythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$env:PYINSTALLER_CONFIG_DIR = Join-Path $ProjectRoot ".pyinstaller-cache"

if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string] $FilePath,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]] $Arguments
    )

    & $FilePath @Arguments

    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $FilePath $Arguments"
    }
}

Write-Host "[build] Checking PyInstaller..."
Invoke-Checked -FilePath $pythonExe -Arguments @("-m", "PyInstaller", "--version") | Out-Null

Write-Host "[build] Building $exeName.exe..."
Invoke-Checked -FilePath $pythonExe -Arguments @(
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--onefile",
    "--windowed",
    "--name",
    $exeName,
    "--add-data",
    "tiles;tiles",
    $entryPoint
)

Write-Host "[build] Done: dist\$exeName.exe"
