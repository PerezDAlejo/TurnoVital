param(
  [switch]$Aggressive
)

Write-Host "Cleaning caches and logs..."
Get-ChildItem -Recurse -Force -Include "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Force -Include "*.pyc","*.pyo","*.pyd" | Remove-Item -Force -ErrorAction SilentlyContinue
if (Test-Path ".\agendamiento.log") { Remove-Item ".\agendamiento.log" -Force }
if ($Aggressive) {
  Write-Host "Aggressive mode: removing build/test artifacts"
  if (Test-Path ".\.aws-sam") { Remove-Item ".\.aws-sam" -Recurse -Force }
  if (Test-Path ".\.pytest_cache") { Remove-Item ".\.pytest_cache" -Recurse -Force }
  if (Test-Path ".\htmlcov") { Remove-Item ".\htmlcov" -Recurse -Force }
  if (Test-Path ".\build") { Remove-Item ".\build" -Recurse -Force }
  if (Test-Path ".\dist") { Remove-Item ".\dist" -Recurse -Force }
}
Write-Host "Done."
