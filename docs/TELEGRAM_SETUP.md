# Configuracao das credenciais do Telegram (pendente desde a Fase 1)

Este passo e rapido e pode ser feito em paralelo com o resto do Gate 2.

## 1. Criar o bot

1. Abra o Telegram e procure por `@BotFather`.
2. Envie `/newbot` e siga as instrucoes (nome + username do bot).
3. O BotFather vai te dar um **token** parecido com `123456789:ABCdefGhIJKlmNoPQRstuVwxyZ`.

## 2. Pegar o chat_id

1. Envie qualquer mensagem para o bot que voce acabou de criar.
2. Abra no navegador:
   `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
3. Procure o campo `"chat":{"id": ... }` na resposta JSON. Esse numero e o `chat_id`.

## 3. Preencher no config.yaml LOCAL

**Nunca commite o token/chat_id real no repositorio.** Edite apenas o seu
`config.yaml` local (esse arquivo ja deveria estar no `.gitignore`):

```yaml
telegram:
  bot_token: "SEU_TOKEN_AQUI"
  chat_id: "SEU_CHAT_ID_AQUI"
```

## 4. Testar

Rode o notifier localmente (`python -m notifier.telegram_notifier` ou o modulo
equivalente do seu projeto) e confirme que a mensagem de teste chega no seu
Telegram. Se nao chegar, confira se o bot_token esta correto e se voce mandou
pelo menos uma mensagem ao bot antes de consultar o `getUpdates`.
