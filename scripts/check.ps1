$ErrorActionPreference = "Stop"
Push-Location backend
try {
  python -m pytest
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  python -m ruff check app tests
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  python -m mypy app
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { Pop-Location }

Push-Location frontend
try {
  npm run lint
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  npm run build
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { Pop-Location }
