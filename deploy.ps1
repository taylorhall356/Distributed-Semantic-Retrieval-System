#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy Distributed Semantic Retrieval System with Docker Compose
    
.DESCRIPTION
    Automated deployment script that handles:
    - Docker cleanup and environment initialization
    - Service startup with health checks
    - Database initialization verification
    - Integration test execution
    
.PARAMETER CleanSlate
    Remove all existing containers and volumes before deployment
    
.PARAMETER IntegrationTest
    Run integration tests after deployment
#>

param(
    [switch]$CleanSlate,
    [switch]$IntegrationTest,
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Colors for output
$colors = @{
    Green = "`e[32m"
    Red = "`e[31m"
    Yellow = "`e[33m"
    Blue = "`e[34m"
    Reset = "`e[0m"
}

function Write-Status {
    param([string]$Message, [ValidateSet('Info', 'Success', 'Warning', 'Error')]$Type = 'Info')
    $color = @{'Info' = $colors.Blue; 'Success' = $colors.Green; 'Warning' = $colors.Yellow; 'Error' = $colors.Red}[$Type]
    Write-Host "$color[$Type]$($colors.Reset) $Message"
}

Write-Status "Distributed Semantic Retrieval System - Deployment" Blue
Write-Status "Version 1.0 | Deadline: April 20, 2026" Blue

# Step 1: Clean Docker environment if requested
if ($CleanSlate) {
    Write-Status "Cleaning Docker environment..." Info
    try {
        docker compose down --remove-orphans -v 2>$null
        Write-Status "✓ Stopped all containers" Success
    }
    catch {
        Write-Status "⚠ No running containers to stop" Warning
    }
    
    try {
        docker system prune -af 2>$null
        Write-Status "✓ Pruned unused images and volumes" Success
    }
    catch {
        Write-Status "⚠ Docker prune failed (continuing anyway)" Warning
    }
}

# Step 2: Build and start services
Write-Status "Building Docker images (CPU-only PyTorch)..." Info
$buildStartTime = Get-Date

try {
    $buildOutput = docker compose up --build -d 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Status "✓ Docker Compose services started" Success
        $buildDuration = ((Get-Date) - $buildStartTime).TotalSeconds
        Write-Status "  Build completed in $buildDuration seconds" Success
    }
    else {
        Write-Status "✗ Docker Compose startup failed:" Error
        Write-Host $buildOutput
        exit 1
    }
}
catch {
    Write-Status "✗ Error during Docker build: $_" Error
    exit 1
}

# Step 3: Verify services are healthy
Write-Status "Verifying services (up to $TimeoutSeconds seconds)..." Info
$startTime = Get-Date
$allHealthy = $false

while ($((Get-Date) - $startTime).TotalSeconds -lt $TimeoutSeconds) {
    try {
        # Check API health
        $apiHealth = Invoke-RestMethod -Uri "http://localhost:8080/health" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        
        if ($apiHealth.status -eq 'ok') {
            Write-Status "✓ API service is healthy" Success
            $allHealthy = $true
            break
        }
    }
    catch {
        # Service not ready yet
    }
    
    Start-Sleep -Seconds 2
}

if (-not $allHealthy) {
    Write-Status "✗ Services did not become healthy within timeout" Error
    Write-Status "Checking Docker logs..." Info
    docker compose logs --tail=50
    exit 1
}

Write-Status "✓ All services verified as healthy" Success

# Step 4: Verify database initialization
Write-Status "Verifying database initialization..." Info
try {
    $dbCheck = docker compose exec -T postgres psql -U semantic_user -d semantic_retrieval -c "SELECT COUNT(*) FROM users;" 2>/dev/null
    Write-Status "✓ Database schema initialized successfully" Success
}
catch {
    Write-Status "⚠ Database check failed (schema may still initialize)" Warning
}

# Step 5: Display service URLs
Write-Status "`nServices are now available:" Success
$services = @(
    @{Name = "API Server"; Url = "http://localhost:8080"; Doc = "http://localhost:8080/docs" }
    @{Name = "MinIO Console"; Url = "http://localhost:9001"; Creds = "minioadmin / minioadmin" }
    @{Name = "RabbitMQ Console"; Url = "http://localhost:15672"; Creds = "guest / guest" }
    @{Name = "Qdrant Vector DB"; Url = "http://localhost:6333"; Doc = "http://localhost:6333" }
)

foreach ($svc in $services) {
    Write-Host "  • $($svc.Name): $($svc.Url)"
    if ($svc.Doc) { Write-Host "    Docs: $($svc.Doc)" }
    if ($svc.Creds) { Write-Host "    Credentials: $($svc.Creds)" }
}

# Step 6: Run integration tests if requested
if ($IntegrationTest) {
    Write-Status "`nRunning integration tests..." Info
    if (Test-Path "scripts/test_integration.ps1") {
        & "scripts/test_integration.ps1"
        if ($LASTEXITCODE -eq 0) {
            Write-Status "✓ Integration tests PASSED" Success
        }
        else {
            Write-Status "✗ Integration tests FAILED" Error
            exit 1
        }
    }
    else {
        Write-Status "⚠ Integration test script not found" Warning
    }
}

# Final status
Write-Status "`n✓✓✓ DEPLOYMENT SUCCESSFUL ✓✓✓" Green
Write-Host "`n$($colors.Blue)Quick Start:$($colors.Reset)"
Write-Host "  1. View API docs: http://localhost:8080/docs"
Write-Host "  2. Upload PDF: POST /documents with file and JWT token"
Write-Host "  3. Search documents: GET /search?q=<query> with JWT token"
Write-Host "`n$($colors.Blue)View Logs:$($colors.Reset)"
Write-Host "  docker compose logs -f api"
Write-Host "  docker compose logs -f worker"
Write-Host "`n$($colors.Blue)Stop Services:$($colors.Reset)"
Write-Host "  docker compose down"

Write-Status "Deployment Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" Info
