"""
API Dona Memória — hospede no Render para guardar dados entre sessões da Alexa.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, jsonify, request

app = Flask(__name__)

API_SECRET = os.environ.get("API_SECRET", "")
DATABASE_PATH = os.environ.get("DATABASE_PATH", "dona_memoria.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def usar_postgres():
    return DATABASE_URL.startswith("postgres")


def verificar_chave():
    if not API_SECRET:
        return True
    return request.headers.get("X-API-Key") == API_SECRET


def resposta_nao_autorizado():
    return jsonify({"erro": "nao autorizado"}), 401


def init_db():
    if usar_postgres():
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                user_id TEXT PRIMARY KEY,
                dados JSONB NOT NULL DEFAULT '{}',
                atualizado_em TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        conn.commit()
        cur.close()
        conn.close()
    else:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                user_id TEXT PRIMARY KEY,
                dados TEXT NOT NULL DEFAULT '{}',
                atualizado_em TEXT
            )
            """
        )
        conn.commit()
        conn.close()


def ler_usuario(user_id):
    if usar_postgres():
        import psycopg2
        from psycopg2.extras import Json, RealDictCursor

        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        cur.execute("SELECT dados FROM usuarios WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return {"people": {}, "memoria": {}}
        dados = row["dados"]
        if isinstance(dados, str):
            dados = json.loads(dados)
        return dados

    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()
    cur.execute("SELECT dados FROM usuarios WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"people": {}, "memoria": {}}
    return json.loads(row[0])


def gravar_usuario(user_id, dados):
    agora = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(dados, ensure_ascii=False)

    if usar_postgres():
        import psycopg2
        from psycopg2.extras import Json

        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO usuarios (user_id, dados, atualizado_em)
            VALUES (%s, %s, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET dados = EXCLUDED.dados, atualizado_em = NOW()
            """,
            (user_id, Json(dados)),
        )
        conn.commit()
        cur.close()
        conn.close()
        return

    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute(
        """
        INSERT INTO usuarios (user_id, dados, atualizado_em)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET dados = excluded.dados, atualizado_em = excluded.atualizado_em
        """,
        (user_id, payload, agora),
    )
    conn.commit()
    conn.close()


@app.before_request
def setup_db():
    if not getattr(app, "_db_ok", False):
        init_db()
        app._db_ok = True


@app.get("/")
def health():
    return jsonify({"status": "ok", "servico": "dona-memoria-api"})


@app.get("/api/users/<user_id>")
def obter_dados(user_id):
    if not verificar_chave():
        return resposta_nao_autorizado()
    dados = ler_usuario(user_id)
    return jsonify({"user_id": user_id, "dados": dados})


@app.put("/api/users/<user_id>")
def salvar_dados(user_id):
    if not verificar_chave():
        return resposta_nao_autorizado()
    body = request.get_json(silent=True) or {}
    dados = body.get("dados", body)
    if "people" not in dados:
        dados.setdefault("people", {})
    if "memoria" not in dados:
        dados.setdefault("memoria", {})
    gravar_usuario(user_id, dados)
    return jsonify({"ok": True, "user_id": user_id})


@app.get("/api/users/<user_id>/stats")
def obter_estatisticas(user_id):
    if not verificar_chave():
        return resposta_nao_autorizado()
    
    dados = ler_usuario(user_id)
    memoria = dados.get("memoria", {})
    
    # Extrair estatísticas dos dados de memória
    total_time = memoria.get("tempo_total", 0)
    daily_stats = memoria.get("estatisticas_diarias", [])
    
    # Se não houver dados, retornar estrutura vazia
    if not daily_stats:
        daily_stats = []
    
    return jsonify({
        "user_id": user_id,
        "totalTime": total_time,
        "dailyStats": daily_stats
    })


@app.post("/api/users/<user_id>/stats")
def registrar_estatistica(user_id):
    if not verificar_chave():
        return resposta_nao_autorizado()
    
    body = request.get_json(silent=True) or {}
    dados = ler_usuario(user_id)
    
    # Inicializar estrutura de memória se não existir
    if "memoria" not in dados:
        dados["memoria"] = {}
    
    memoria = dados["memoria"]
    
    # Atualizar tempo total
    tempo_adicional = body.get("tempo", 0)
    memoria["tempo_total"] = memoria.get("tempo_total", 0) + tempo_adicional
    
    # Adicionar estatística do dia
    data_hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if "estatisticas_diarias" not in memoria:
        memoria["estatisticas_diarias"] = []
    
    # Procurar se já existe entrada para hoje
    estatisticas_diarias = memoria["estatisticas_diarias"]
    entrada_hoje = None
    for entrada in estatisticas_diarias:
        if entrada.get("date") == data_hoje:
            entrada_hoje = entrada
            break
    
    if entrada_hoje:
        # Atualizar entrada existente
        entrada_hoje["time"] += body.get("tempo", 0)
        entrada_hoje["correct"] += body.get("correct", 0)
        entrada_hoje["wrong"] += body.get("wrong", 0)
    else:
        # Criar nova entrada
        estatisticas_diarias.append({
            "date": data_hoje,
            "time": body.get("tempo", 0),
            "correct": body.get("correct", 0),
            "wrong": body.get("wrong", 0)
        })
    
    gravar_usuario(user_id, dados)
    return jsonify({"ok": True, "user_id": user_id})


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
