param(
    [Parameter(Mandatory = $true)] [SecureString] $LocalStackAuthToken,
    [string] $AppApiKey = "",
    [string] $PostgresPassword = "research",
    [string] $Neo4jPassword = "research-graph-password",
    [string] $ClusterName = "proofgraph"
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$previousLocalStackToken = $env:LOCALSTACK_AUTH_TOKEN

foreach ($command in "docker", "kubectl", "k3d") {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "$command is required. Install it, then run this script again."
    }
}

# This is intentionally process-scoped: the token is never written to a file or Kubernetes Secret.
$tokenBstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($LocalStackAuthToken)
try {
    $env:LOCALSTACK_AUTH_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenBstr)
    docker compose -f (Join-Path $root "infra\localstack\docker-compose.localstack.yml") up -d
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenBstr)
    if ($null -eq $previousLocalStackToken) {
        Remove-Item Env:LOCALSTACK_AUTH_TOKEN -ErrorAction SilentlyContinue
    } else {
        $env:LOCALSTACK_AUTH_TOKEN = $previousLocalStackToken
    }
}

for ($i = 0; $i -lt 30; $i++) {
    try {
        if ((Invoke-WebRequest "http://localhost:4566/_localstack/health" -UseBasicParsing).StatusCode -eq 200) { break }
    } catch {}
    Start-Sleep -Seconds 2
    if ($i -eq 29) { throw "LocalStack did not become healthy." }
}

if (-not (k3d cluster list -o json | ConvertFrom-Json | Where-Object { $_.name -eq $ClusterName })) {
    k3d cluster create $ClusterName --servers 1 --agents 1 --port "8000:30080@loadbalancer" --port "3000:30000@loadbalancer" --wait
}

Set-Location $root
docker build -t proofgraph-research:dev .
docker build -t proofgraph-web:dev .\frontend
k3d image import proofgraph-research:dev -c $ClusterName
k3d image import proofgraph-web:dev -c $ClusterName

$databaseUrl = "postgresql+psycopg://research:$PostgresPassword@postgres:5432/research"
$neo4jAuth = "neo4j/$Neo4jPassword"
kubectl create namespace proofgraph --dry-run=client -o yaml | kubectl apply -f -
kubectl -n proofgraph create secret generic research-secrets `
    --from-literal=POSTGRES_PASSWORD=$PostgresPassword `
    --from-literal=DATABASE_URL=$databaseUrl `
    --from-literal=NEO4J_PASSWORD=$Neo4jPassword `
    --from-literal=NEO4J_AUTH=$neo4jAuth `
    --from-literal=APP_API_KEY=$AppApiKey `
    --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -k (Join-Path $root "k8s\base")
kubectl -n proofgraph rollout status statefulset/postgres --timeout=180s
kubectl -n proofgraph rollout status statefulset/redis --timeout=180s
kubectl -n proofgraph rollout status statefulset/neo4j --timeout=240s
kubectl -n proofgraph rollout status deployment/api --timeout=180s
kubectl -n proofgraph rollout status deployment/worker --timeout=180s
kubectl -n proofgraph rollout status deployment/web --timeout=180s

Write-Host "Deployment complete: http://localhost:8000" -ForegroundColor Green
kubectl -n proofgraph get pods,svc
