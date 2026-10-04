$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
function Invoke-Check([scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Check failed: $Command" }
}
Invoke-Check { npx.cmd --yes npm@12.2.0 ci }
Invoke-Check { npx.cmd --yes npm@12.2.0 run lint }
Invoke-Check { npx.cmd --yes npm@12.2.0 run typecheck }
Invoke-Check { npx.cmd --yes npm@12.2.0 test }
Invoke-Check { npx.cmd --yes npm@12.2.0 run build:web }
Invoke-Check { npx.cmd --yes npm@12.2.0 run build:mobile }
Invoke-Check { node scripts/verify_mobile_surface.mjs }
Invoke-Check { python -m uv sync --project apps/api --frozen --python 3.12.12 }
Push-Location -LiteralPath 'apps/api'
try {
    Invoke-Check { python -m uv run --frozen ruff check . ../../scripts }
    Invoke-Check { python -m uv run --frozen ruff format --check . ../../scripts }
    Invoke-Check { python -m uv run --frozen mypy app }
    Invoke-Check { python -m uv run --project . --frozen ../../scripts/verify_database.py }
    Invoke-Check { python -m uv run --project . --frozen ../../scripts/verify_stack.py }
} finally { Pop-Location }
