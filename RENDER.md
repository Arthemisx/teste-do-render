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

Em **Configuration → Environment variables** da função Lambda:

| Variável | Valor |
|----------|--------|
| `RENDER_API_URL` | `https://sua-api.onrender.com` (sem barra no final) |
| `RENDER_API_KEY` | mesmo valor de `API_SECRET` no Render |

Faça deploy de `lambda_function.py` e `utils.py` atualizados.

## 3. Testar a API

```bash
curl https://SUA-URL.onrender.com/
# {"status":"ok","servico":"dona-memoria-api"}

curl -H "X-API-Key: SEU_SECRET" https://SUA-URL.onrender.com/api/users/teste123
# {"user_id":"teste123","dados":{"people":{},"memoria":{}}}
```

## 4. Testar na Alexa

1. Build do modelo `pt-BR.json`.
2. Abra a skill → cadastre parentes → feche a skill.
3. Abra de novo → os parentes devem continuar cadastrados.

## Observação

No plano free do Render, o serviço pode **dormir** após inatividade (primeira requisição demora ~30s). Para produção, use plano pago ou DynamoDB na AWS.
