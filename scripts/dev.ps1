param([switch]$ConfigureOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath '.env')) {
    $dbPassword = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
    $storagePassword = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
    $template = Get-Content -LiteralPath '.env.example' -Raw
    $template = $template.Replace('POSTGRES_PASSWORD=', "POSTGRES_PASSWORD=$dbPassword")
    $template = $template.Replace('MINIO_ROOT_PASSWORD=', "MINIO_ROOT_PASSWORD=$storagePassword")
    $template = $template.Replace('S3_SECRET_KEY=', "S3_SECRET_KEY=$storagePassword")
    $template = $template.Replace('DATABASE_URL=', "DATABASE_URL=postgresql+psycopg://fleet:${dbPassword}@localhost:5432/fleet_delivery")
    [IO.File]::WriteAllText((Join-Path $projectRoot '.env'), $template)
    Write-Host 'Created local .env with random credentials.'
}
if ($ConfigureOnly) { exit 0 }
docker compose up --build -d --wait --wait-timeout 300
if ($LASTEXITCODE -ne 0) { throw 'Docker stack failed. Check docker compose logs.' }
Write-Host 'Web: http://localhost:3000 | API: http://localhost:8000/docs'
