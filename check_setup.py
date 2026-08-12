"""
check_setup.py

Script de diagnostico rapido. Roda ANTES do coletor para confirmar que:
1. O terminal MT5 esta aberto e logado corretamente.
2. O banco de dados configurado em config.yaml esta acessivel com as credenciais certas.
3. As tabelas do schema.sql realmente existem no banco (schema foi aplicado).

Uso:
    python check_setup.py

Saida: uma lista de checks com [OK] ou [FALHA] e a causa provavel, sem stack trace bruto.
"""
import sys

import yaml


def load_config(path="config/config.yaml"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"[FALHA] Config nao encontrado em '{path}'. "
              f"Copie config/config.example.yaml para config/config.yaml e edite.")
        sys.exit(1)


def check_mt5(cfg):
    print("\n=== 1. Verificando conexao com o MetaTrader 5 ===")
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("[FALHA] Pacote 'MetaTrader5' nao instalado ou rodando fora do Windows.")
        return False

    terminal_path = cfg["mt5"].get("terminal_path")
    ok = mt5.initialize(path=terminal_path) if terminal_path else mt5.initialize()
    if not ok:
        print(f"[FALHA] mt5.initialize() retornou False. Erro: {mt5.last_error()}")
        print("        Verifique se o terminal MT5 esta ABERTO e LOGADO na conta antes de rodar este script.")
        return False

    info = mt5.account_info()
    if info is None:
        print("[FALHA] MT5 inicializado, mas account_info() retornou None (nao logado?).")
        mt5.shutdown()
        return False

    print(f"[OK] Conectado a conta {info.login} ({info.server}) "
          f"saldo={info.balance} equity={info.equity}")

    missing_symbols = []
    for symbol in cfg.get("symbols", []):
        if not mt5.symbol_select(symbol, True):
            missing_symbols.append(symbol)
    if missing_symbols:
        print(f"[AVISO] Simbolos nao encontrados no Market Watch: {missing_symbols}")
        print("        Adicione-os manualmente no MT5 (botao direito -> Mostrar Todos) ou verifique o nome exato.")
    else:
        print(f"[OK] Todos os {len(cfg.get('symbols', []))} simbolos configurados estao disponiveis.")

    mt5.shutdown()
    return len(missing_symbols) == 0


def check_postgres(cfg):
    print("\n=== 2. Verificando conexao com PostgreSQL/TimescaleDB ===")
    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("[FALHA] Pacote 'sqlalchemy' nao instalado. Rode: pip install -r requirements.txt")
        return False, None

    d = cfg["database"]
    url = f"postgresql+psycopg2://{d['user']}:{d['password']}@{d['host']}:{d['port']}/{d['dbname']}"
    engine = create_engine(url)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        msg = str(e)
        print(f"[FALHA] Nao foi possivel conectar em {d['host']}:{d['port']}/{d['dbname']}.")
        if "password authentication failed" in msg:
            print("        Causa provavel: a porta configurada esta sendo atendida por OUTRO Postgres "
                  "(nao o do docker-compose), com senha diferente. Confira se subiu o compose certo "
                  "(test=5433, prod=5432) e se a porta em config.yaml corresponde.")
        elif "Connection refused" in msg or "could not connect" in msg:
            print("        Causa provavel: nenhum servico Postgres esta rodando nessa porta. "
                  "Rode: docker compose -f docker-compose.test.yml up -d (ou docker-compose.prod.yml)")
        else:
            print(f"        Detalhe: {msg.splitlines()[0]}")
        return False, None

    print(f"[OK] Conectado em {d['host']}:{d['port']}/{d['dbname']} com sucesso.")
    return True, engine


def check_tables(engine):
    print("\n=== 3. Verificando se o schema.sql foi aplicado ===")
    from sqlalchemy import text

    expected_tables = [
        "candles", "indicators", "correlations", "portfolio_var",
        "signals", "equity_curve", "anomaly_log", "economic_events",
    ]
    try:
        with engine.connect() as conn:
            existing = {
                row[0] for row in conn.execute(text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
                ))
            }
    except Exception as e:
        print(f"[FALHA] Erro ao consultar tabelas: {e}")
        return False

    missing = [t for t in expected_tables if t not in existing]
    if missing:
        print(f"[FALHA] Tabelas ausentes: {missing}")
        print("        Rode: psql -h <host> -p <porta> -U postgres -d <dbname> -f database/schema.sql")
        return False

    print(f"[OK] Todas as {len(expected_tables)} tabelas esperadas existem no banco.")
    return True


def main():
    print("Diagnostico de setup - CFD Adaptive System")
    cfg = load_config()

    mt5_ok = check_mt5(cfg)
    pg_ok, engine = check_postgres(cfg)
    tables_ok = check_tables(engine) if pg_ok else False

    print("\n=== Resumo ===")
    print(f"MT5:      {'OK' if mt5_ok else 'FALHA'}")
    print(f"Postgres: {'OK' if pg_ok else 'FALHA'}")
    print(f"Schema:   {'OK' if tables_ok else 'FALHA'}")

    if mt5_ok and pg_ok and tables_ok:
        print("\nTudo certo! Pode rodar: python collector/mt5_collector.py")
        sys.exit(0)
    else:
        print("\nCorrija os itens marcados como FALHA antes de rodar o coletor.")
        sys.exit(1)


if __name__ == "__main__":
    main()
