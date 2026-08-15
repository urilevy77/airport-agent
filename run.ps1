# Local development on Windows: FastAPI on 5001, Vite on 5173 proxying /chat to it.
# Open http://localhost:5173
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (Test-Path .env) {
  foreach ($line in Get-Content .env) {
    if ($line -match '^\s*([^#=\s][^=]*)=(.*)$') {
      $name = $matches[1].Trim()
      $value = $matches[2].Trim().Trim('"').Trim("'")
      Set-Item -Path "env:$name" -Value $value
    }
  }
}

if (-not $env:ANTHROPIC_API_KEY) {
  Write-Error "Set ANTHROPIC_API_KEY first: put it in .env or `$env:ANTHROPIC_API_KEY = '...'"
  exit 1
}

$api = Start-Process -PassThru -FilePath "python" `
  -ArgumentList "-m", "uvicorn", "server.app:app", "--port", "5001", "--reload"

try {
  Set-Location frontend
  npm run dev
} finally {
  if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue }
}
