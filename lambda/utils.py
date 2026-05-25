import logging
import json
import os
import random
import re
import unicodedata

import requests

logger = logging.getLogger(__name__)

# OpenRouter — use OPENROUTER_API_KEY na Lambda em produção.
API_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    "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",
)

# API no Render para memória permanente entre sessões.
RENDER_API_URL = os.environ.get("RENDER_API_URL", "").rstrip("/")
RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "")


def normalizar_texto(texto):
    """Remove acentos, pontuação e deixa minúsculo para comparação flexível."""
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    sem_acento = sem_acento.lower()
    sem_acento = re.sub(r"[^\w\s]", " ", sem_acento)
    return re.sub(r"\s+", " ", sem_acento).strip()


def extrair_palavras(texto):
    """Separa o texto em palavras, com ou sem vírgulas."""
    return [p for p in normalizar_texto(texto).split() if p]


def limpar_lista_palavras(palavras):
    """Garante que cada item da lista seja uma palavra isolada."""
    resultado = []
    for item in palavras:
        resultado.extend(extrair_palavras(item))
    return resultado


def _chamar_openrouter(prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
    }
    r = requests.post(url, headers=headers, data=json.dumps(data), timeout=12)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def gerar_palavras_aleatorias(quantidade):
    """Gera palavras para o jogo de memorização."""
    prompt = f"""
    Gere uma lista de {quantidade} palavras simples em português, comuns e fáceis de lembrar.
    Responda APENAS com as palavras separadas por vírgula, sem explicações.
    Exemplo: casa, cachorro, sol
    """
    try:
        texto = _chamar_openrouter(prompt)
        texto = texto.replace(" e ", ",").replace("\n", ",")
        palavras_brutas = re.split(r"[,;]+", texto)
        palavras = limpar_lista_palavras(palavras_brutas)
        if len(palavras) < quantidade:
            palavras = extrair_palavras(texto)
        return palavras[:quantidade]
    except Exception as e:
        logging.error(f"Erro ao gerar palavras: {e}")
        padrao = {
            3: ["casa", "cachorro", "sol"],
            5: ["casa", "cachorro", "sol", "arvore", "livro"],
            7: ["casa", "cachorro", "sol", "arvore", "livro", "computador", "flor"],
        }
        return padrao.get(quantidade, ["casa", "cachorro", "sol"])


def interpretar_confirmacao(texto):
    """Retorna 'sim', 'nao' ou None."""
    if not texto:
        return None

    t = texto.lower().strip()
    negativas = (
        "não quero", "nao quero", "não", "nao", "negativo",
        "desisto", "cancelar", "cancela", "parar", "pare",
    )
    for expressao in negativas:
        if expressao in t:
            return "nao"

    positivas = (
        "nível médio", "nivel medio", "nível difícil", "nivel dificil",
        "quero ir", "vamos para", "continuar", "aceito", "ótimo", "otimo",
        "claro", "pode", "vamos", "bora", "quero", "médio", "medio",
        "difícil", "dificil", "sim", "ok",
    )
    for expressao in positivas:
        if expressao in t:
            return "sim"
    return None


def interpretar_escolha_jogo(texto):
    """Retorna 'memoria', 'parentes' ou None."""
    if not texto:
        return None
    t = texto.lower().strip()
    if any(x in t for x in ("parente", "família", "familia", "filho", "filha", "cadastr")):
        return "parentes"
    if any(x in t for x in ("palavra", "memor", "memória", "memoria")):
        return "memoria"
    return None


def interpretar_pronto_parentes(texto):
    if not texto:
        return False
    t = texto.lower().strip()
    return any(x in t for x in ("pronto", "começar", "comecar", "cadastrei", "pode começar", "iniciar"))


def obter_nomes_por_relacao(people, relacao):
    valor = people.get(relacao, [])
    if isinstance(valor, str):
        return [valor]
    return list(valor)


def render_disponivel():
    return bool(RENDER_API_URL and RENDER_API_KEY)


def _headers_render():
    return {"X-API-Key": RENDER_API_KEY, "Content-Type": "application/json"}


def carregar_dados_usuario(user_id):
    """Carrega parentes e progresso salvos no Render."""
    vazio = {"people": {}, "memoria": {}}
    if not user_id or not render_disponivel():
        return vazio
    try:
        url = f"{RENDER_API_URL}/api/users/{user_id}"
        r = requests.get(url, headers=_headers_render(), timeout=10)
        if r.status_code == 200:
            dados = r.json().get("dados", vazio)
            dados.setdefault("people", {})
            dados.setdefault("memoria", {})
            return dados
        logging.warning(f"Render GET {r.status_code}: {r.text}")
    except Exception as e:
        logging.error(f"Erro ao carregar do Render: {e}")
    return vazio


def salvar_dados_usuario(user_id, dados):
    """Salva parentes e progresso no Render."""
    if not user_id or not render_disponivel():
        return False
    try:
        url = f"{RENDER_API_URL}/api/users/{user_id}"
        payload = {
            "dados": {
                "people": dados.get("people", {}),
                "memoria": dados.get("memoria", {}),
            }
        }
        r = requests.put(url, headers=_headers_render(), json=payload, timeout=10)
        if r.status_code == 200:
            return True
        logging.warning(f"Render PUT {r.status_code}: {r.text}")
    except Exception as e:
        logging.error(f"Erro ao salvar no Render: {e}")
    return False


def adicionar_parente(people, relacao, nome):
    """Adiciona parente; permite vários nomes na mesma relação."""
    nome = nome.strip()
    if not nome:
        return people
    if relacao not in people:
        people[relacao] = nome
    else:
        existente = people[relacao]
        if isinstance(existente, list):
            if nome not in existente:
                existente.append(nome)
        elif existente != nome:
            people[relacao] = [existente, nome]
    return people


def formatar_parentes_cadastrados(people):
    if not people:
        return "nenhum parente cadastrado"
    partes = []
    for relacao, nomes in people.items():
        lista = obter_nomes_por_relacao(people, relacao)
        partes.append(f"{relacao}: {', '.join(lista)}")
    return "; ".join(partes)


def gerar_pergunta_parentes(people):
    """
    Gera pergunta sobre parentes cadastrados (IA com fallback).
    Retorna dict: pergunta, relacao, nomes_esperados.
    """
    relacoes = list(people.keys())
    if not relacoes:
        return None

    relacao = random.choice(relacoes)
    nomes = obter_nomes_por_relacao(people, relacao)
    contexto = formatar_parentes_cadastrados(people)

    try:
        prompt = f"""
        Você ajuda idosos a treinar a memória sobre a família.
        Parentes cadastrados: {contexto}.
        Crie UMA pergunta curta e clara em português sobre a relação "{relacao}".
        A resposta correta envolve estes nomes: {", ".join(nomes)}.
        Exemplos de estilo: "Qual o nome do seu filho?" ou "Quais os nomes dos seus filhos?"
        Responda APENAS com a pergunta, sem aspas nem explicações.
        """
        pergunta = _chamar_openrouter(prompt)
        if not pergunta.endswith("?"):
            pergunta = pergunta.rstrip(".") + "?"
    except Exception as e:
        logging.error(f"Erro ao gerar pergunta de parentes: {e}")
        if len(nomes) > 1:
            pergunta = f"Quais os nomes dos seus {relacao}s?"
        else:
            pergunta = f"Qual o nome do seu {relacao}?"

    return {
        "pergunta": pergunta,
        "relacao": relacao,
        "nomes_esperados": nomes,
    }


def verificar_resposta(palavras_esperadas, resposta_usuario):
    """Verifica palavras do jogo de memorização."""
    if not resposta_usuario:
        return False

    esperadas = limpar_lista_palavras(palavras_esperadas)
    ditas = extrair_palavras(resposta_usuario)
    if not esperadas or not ditas:
        return False

    for palavra in esperadas:
        if palavra not in ditas:
            return False
    return True


def verificar_nome_parente(nomes_esperados, resposta_usuario):
    """Verifica se o usuário citou os nomes esperados dos parentes."""
    if not resposta_usuario:
        return False

    ditas = extrair_palavras(resposta_usuario)
    if not ditas:
        return False

    for nome in nomes_esperados:
        tokens = extrair_palavras(nome)
        for token in tokens:
            if token not in ditas:
                return False
    return True
