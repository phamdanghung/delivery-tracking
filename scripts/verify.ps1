$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
function Invoke-Check([scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Check failed: $Command" }
}
Invoke-Check { npm.cmd ci }
Invoke-Check { npm.cmd run lint }
Invoke-Check { npm.cmd run typecheck }
Invoke-Check { npm.cmd test }
Invoke-Check { npm.cmd run build:web }
Invoke-Check { npm.cmd run build:mobile }
Invoke-Check { python -m uv sync --project apps/api --frozen --python 3.12.12 }
Push-Location -LiteralPath 'apps/api'
try {
    Invoke-Check { python -m uv run --frozen ruff check . }
    Invoke-Check { python -m uv run --frozen ruff format --check . }
    Invoke-Check { python -m uv run --frozen mypy app }
    Invoke-Check { python -m uv run --frozen pytest }
} finally { Pop-Location }
