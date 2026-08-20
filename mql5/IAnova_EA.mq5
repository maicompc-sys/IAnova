//+------------------------------------------------------------------+
//| IAnova_EA.mq5                                                      |
//| Esqueleto do EA "fino" de execucao (Fase 3).                        |
//| O Python decide (motor tecnico / ensemble RL); este EA APENAS       |
//| executa e gerencia stop/take. Nenhuma logica de decisao aqui.       |
//| STATUS: nao compilado/testado. Nao usar em conta real.              |
//+------------------------------------------------------------------+
#property copyright "IAnova"
#property version   "0.01"
#property strict

input string PipeName        = "\\\\.\\pipe\\ianova_signals"; // named pipe / socket com o Python
input double MaxSpreadPoints = 30;                            // trava por spread excessivo
input int    MagicNumber     = 202608;

int pipeHandle = INVALID_HANDLE;

int OnInit()
{
   // TODO: abrir conexao com named pipe ou WebSocket para receber sinais do Python.
   Print("IAnova_EA: OnInit - esqueleto, comunicacao ainda nao implementada.");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if (pipeHandle != INVALID_HANDLE)
      FileClose(pipeHandle);
}

//+------------------------------------------------------------------+
//| Pre-trade checks obrigatorios antes de qualquer ordem              |
//+------------------------------------------------------------------+
bool PreTradeChecks(string symbol, double volume)
{
   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if (freeMargin <= 0)
   {
      Print("IAnova_EA: margem insuficiente, ordem bloqueada.");
      return false;
   }

   double spread = (double)SymbolInfoInteger(symbol, SYMBOL_SPREAD);
   if (spread > MaxSpreadPoints)
   {
      Print("IAnova_EA: spread acima do limite (", spread, " > ", MaxSpreadPoints, "), ordem bloqueada.");
      return false;
   }

   if (!SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE))
   {
      Print("IAnova_EA: simbolo fora de horario/modo de negociacao, ordem bloqueada.");
      return false;
   }

   // TODO: validar tambem se o simbolo esta selecionado (SymbolSelect) e se
   // ha correlacao/limite de exposicao vindo do risk manager em Python.
   return true;
}

//+------------------------------------------------------------------+
//| Registro auditavel de execucao (ticket, preco real vs esperado)   |
//+------------------------------------------------------------------+
void LogExecution(ulong ticket, double expectedPrice, double actualPrice)
{
   double slippage = actualPrice - expectedPrice;
   // TODO: gravar em arquivo/pipe de volta para o Python persistir na tabela `signals`
   // (ticket MT5, preco esperado, preco real, slippage, horario exato).
   PrintFormat("IAnova_EA: ticket=%d esperado=%.5f real=%.5f slippage=%.5f",
               ticket, expectedPrice, actualPrice, slippage);
}

void OnTick()
{
   // TODO: ler sinal recebido do Python via pipe/socket.
   // TODO: se houver sinal novo -> PreTradeChecks -> enviar ordem -> LogExecution.
   // TODO: health-check periodico de latencia MT5 <-> coletor <-> banco,
   // com alerta Telegram se qualquer elo cair (ver docs/INFRA_PENDENTE.md).
}
