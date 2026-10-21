$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Missing .venv: create a Python 3.12 environment and install requirements-lock.txt; see docs/REPRODUCTION.md.'
}
$env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
& $taskPython -m pytest -q --basetemp='.pytest_tmp'
if ($LASTEXITCODE -ne 0) { throw 'Tests failed. See test output.' }
& $taskPython -m dataco.cli run
if ($LASTEXITCODE -ne 0) { throw 'Pipeline failed. See reports and CLI output.' }
Write-Output 'Complete: reports/analysis_report.html'

