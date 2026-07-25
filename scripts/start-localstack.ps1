param(
    [Parameter(Mandatory = $true)] [SecureString] $LocalStackAuthToken
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$previousToken = $env:LOCALSTACK_AUTH_TOKEN
$tokenBstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($LocalStackAuthToken)

try {
    # Process-scoped only: the LocalStack token is never written to .env or Git.
    $env:LOCALSTACK_AUTH_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenBstr)
    docker compose -f (Join-Path $root "infra\localstack\docker-compose.localstack.yml") up -d
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenBstr)
    if ($null -eq $previousToken) {
        Remove-Item Env:LOCALSTACK_AUTH_TOKEN -ErrorAction SilentlyContinue
    } else {
        $env:LOCALSTACK_AUTH_TOKEN = $previousToken
    }
}

for ($i = 0; $i -lt 30; $i++) {
    try {
        if ((Invoke-WebRequest "http://localhost:4566/_localstack/health" -UseBasicParsing).StatusCode -eq 200) {
            Write-Host "LocalStack is ready: http://localhost:4566" -ForegroundColor Green
            exit 0
        }
    } catch {}
    Start-Sleep -Seconds 2
}

throw "LocalStack did not become healthy. Run 'docker compose -f infra/localstack/docker-compose.localstack.yml logs'."
