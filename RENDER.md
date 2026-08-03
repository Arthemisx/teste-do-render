# Persistência com Render (Dona Memória)

A Alexa (Lambda) **não guarda dados para sempre** sozinha. O Render hospeda uma **API + banco** que lembra os parentes cadastrados mesmo depois de fechar a skill.

## Arquitetura

```
Usuário fala na Alexa → AWS Lambda → API no Render → PostgreSQL
```

Cada usuário tem um `user_id` único da Amazon. A API salva os parentes nesse id.

## 1. Publicar a API no Render

1. Crie conta em [render.com](https://render.com).
2. **New +** → **Blueprint** (ou Web Service).
3. Conecte o repositório Git ou faça upload da pasta `render-api/`.
4. O arquivo `render.yaml` cria:
   - Web Service `dona-memoria-api`
   - Banco PostgreSQL `dona-memoria-db`
5. Após o deploy, copie:
   - **URL** do serviço (ex: `https://dona-memoria-api.onrender.com`)
   - **API_SECRET** (Environment → `API_SECRET`)

## 2. Configurar a Lambda (AWS)

A URL e a chave da API já estão **hardcoded** em `lambda/utils.py`:

| Variável | Valor (no código) |
|----------|-------------------|
| `RENDER_API_URL` | `https://teste-do-render.onrender.com` |
| `RENDER_API_KEY` | `dona-memoria-api-key-2026` |

Se tiver acesso à Lambda, pode sobrescrever via variáveis de ambiente. Caso contrário, basta fazer deploy de `lambda_function.py` e `utils.py` atualizados.

## 3. Exportar PDF

Peça à Alexa: **"Alexa, pedir dona memória para exportar relatório"** ou **"gerar pdf"**.

A skill informará um link como:
`https://teste-do-render.onrender.com/api/users/SEU_ID/pdf`

Abra no navegador do celular ou computador para baixar o PDF.

## 4. Testar a API

```bash
curl https://teste-do-render.onrender.com/
# {"status":"ok","servico":"dona-memoria-api"}

curl -H "X-API-Key: dona-memoria-api-key-2026" https://teste-do-render.onrender.com/api/users/teste123
# {"user_id":"teste123","dados":{"people":{},"memoria":{}}}

# PDF (abre no navegador, sem chave de API):
# https://teste-do-render.onrender.com/api/users/teste123/pdf
```

## 5. Testar na Alexa

1. Build do modelo `pt-BR.json`.
2. Abra a skill → cadastre parentes → feche a skill.
3. Abra de novo → os parentes devem continuar cadastrados.

## Observação

No plano free do Render, o serviço pode **dormir** após inatividade (primeira requisição demora ~30s). Para produção, use plano pago ou DynamoDB na AWS.
