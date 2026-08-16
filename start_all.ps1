# =============================================================================
# IAnova - start_all.ps1
# Sobe infraestrutura Docker + 3 processos Python em terminais separados.
# Execute com: .\start_all.ps1
# =============================================================================

$ROOT = $PSScriptRoot
$VENV_ACTIVATE = Join-Path $ROOT "venv\Scripts\Activate.ps1"
$COMPOSE_FILE  = Join-Path $ROOT "docker-compose.test.yml"
$SCHEMA_FILE   = Join-Path $ROOT "database\schema.sql"

# --- Cores -------------------------------------------------------------------
function Write-Step  { param($msg) Write-Host "`n[>>] $msg" -ForegroundColor Cyan    }
function Write-Ok    { param($msg) Write-Host "[ OK ] $msg"  -ForegroundColor Green   }
function Write-Warn  { param($msg) Write-Host "[WARN] $msg"  -ForegroundColor Yellow  }
function Write-Fail  { param($msg) Write-Host "[ERRO] $msg"  -ForegroundColor Red     }

# =============================================================================
# 1. Verificar Docker Desktop
# =============================================================================
Write-Step "Verificando Docker..."

$dockerRunning = $false
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerRunning = $true }
} catch {}

if (-not $dockerRunning) {
    Write-Warn "Docker Desktop nao esta rodando. Tentando iniciar..."
    $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerExe) {
        Start-Process $dockerExe
        Write-Host "  Aguardando Docker inicializar (ate 60s)..." -ForegroundColor DarkGray
        $timeout = 60
        $elapsed = 0
        while ($elapsed -lt $timeout) {
            Start-Sleep -Seconds 3
            $elapsed += 3
            try {
                $null = docker info 2>&1
                if ($LASTEXITCODE -eq 0) { $dockerRunning = $true; break }
            } catch {}
            Write-Host "  ... $elapsed s" -ForegroundColor DarkGray
        }
    }
    if (-not $dockerRunning) {
        Write-Fail "Docker nao iniciou. Abra o Docker Desktop manualmente e re-execute o script."
        exit 1
    }
}
Write-Ok "Docker esta rodando."

# =============================================================================
# 2. Subir containers (TimescaleDB :5433 + Redis :6380)
# =============================================================================
Write-Step "Subindo containers Docker (docker-compose.test.yml)..."

docker compose -f $COMPOSE_FILE up -d 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }

if ($LASTEXITCODE -ne 0) {
    Write-Fail "Falha ao subir containers. Verifique o Docker."
    exit 1
}
Write-Ok "Containers iniciados."

# =============================================================================
# 3. Health-check: aguardar PostgreSQL aceitar conexoes
# =============================================================================
Write-Step "Aguardando PostgreSQL ficar pronto na porta 5433..."

$pg_ready = $false
$max_tries = 20
for ($i = 1; $i -le $max_tries; $i++) {
    $result = docker exec cfd_timescaledb_test pg_isready -U postgres -d cfd_system_test 2>&1
    if ($LASTEXITCODE -eq 0) {
        $pg_ready = $true
        break
    }
    Write-Host "  Tentativa $i/$max_tries - banco ainda inicializando..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 3
}

if (-not $pg_ready) {
    Write-Fail "Banco nao ficou pronto a tempo. Tente novamente em alguns segundos."
    exit 1
}
Write-Ok "PostgreSQL pronto."

# =============================================================================
# 4. Aplicar schema (apenas se tabela 'candles' ainda nao existir)
# =============================================================================
Write-Step "Verificando schema do banco..."

$tableExists = docker exec cfd_timescaledb_test psql -U postgres -d cfd_system_test -tAc `
    "SELECT 1 FROM information_schema.tables WHERE table_name='candles';" 2>&1

if ($tableExists.Trim() -ne "1") {
    Write-Warn "Tabelas nao encontradas. Aplicando schema..."
    Get-Content $SCHEMA_FILE | docker exec -i cfd_timescaledb_test psql -U postgres -d cfd_system_test 2>&1 | `
        ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    Write-Ok "Schema aplicado."
} else {
    Write-Ok "Schema ja existe, pulando."
}

# =============================================================================
# 5. Abrir 3 terminais com os processos Python
# =============================================================================
Write-Step "Iniciando processos Python em terminais separados..."

# Bloco de codigo que cada terminal vai executar
$block_collector = @"
`$host.UI.RawUI.WindowTitle = 'IAnova | Coletor MT5'
Set-Location '$ROOT'
& '$VENV_ACTIVATE'
Write-Host '[IAnova] Coletor MT5 iniciado' -ForegroundColor Cyan
python -m collector.mt5_collector
Write-Host '[IAnova] Coletor encerrado. Pressione Enter para fechar.' -ForegroundColor Yellow
Read-Host
"@

$block_indicator = @"
`$host.UI.RawUI.WindowTitle = 'IAnova | Indicadores'
Set-Location '$ROOT'
& '$VENV_ACTIVATE'
Write-Host '[IAnova] Motor de Indicadores iniciado' -ForegroundColor Cyan
python -m engine.indicator_engine
Write-Host '[IAnova] Indicadores encerrado. Pressione Enter para fechar.' -ForegroundColor Yellow
Read-Host
"@

$block_correlation = @"
`$host.UI.RawUI.WindowTitle = 'IAnova | Correlacao'
Set-Location '$ROOT'
& '$VENV_ACTIVATE'
Write-Host '[IAnova] Motor de Correlacao iniciado' -ForegroundColor Cyan
python -m engine.correlation_engine
Write-Host '[IAnova] Correlacao encerrado. Pressione Enter para fechar.' -ForegroundColor Yellow
Read-Host
"@

# Codifica em Base64 para passar ao PowerShell sem problemas de escape
function Start-PSWindow {
    param($Title, $Code)
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Code))
    Start-Process powershell.exe -ArgumentList "-NoExit", "-EncodedCommand", $encoded
}

Start-PSWindow "IAnova | Coletor MT5"   $block_collector
Start-Sleep -Milliseconds 500
Start-PSWindow "IAnova | Indicadores"   $block_indicator
Start-Sleep -Milliseconds 500
Start-PSWindow "IAnova | Correlacao"    $block_correlation

# =============================================================================
# 6. Resumo final
# =============================================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "  IAnova esta rodando!" -ForegroundColor Green
Write-Host "------------------------------------------------------------" -ForegroundColor Magenta
Write-Host "  [1] Coletor MT5      -> candles a cada 2s  (porta 5433)"
Write-Host "  [2] Indicadores      -> EMA/RSI/ATR a cada 5s"
Write-Host "  [3] Correlacao       -> matriz a cada 30s"
Write-Host "------------------------------------------------------------" -ForegroundColor Magenta
Write-Host "  Banco : localhost:5433 (cfd_system_test)"
Write-Host "  Redis : localhost:6380 (cfd_redis_test)"
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host ""
