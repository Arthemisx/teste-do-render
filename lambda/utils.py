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

# API no Render — valores fixos (sem depender de variáveis na AWS Lambda).
RENDER_API_URL = os.environ.get(
    "RENDER_API_URL", "https://teste-do-render.onrender.com"
).rstrip("/")
RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "dona-memoria-api-key-2026")


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
        "desisto", "cancelar", "cancela", "parar", "pare", "sair", "tchau",
    )
    for expressao in negativas:
        if expressao in t:
            return "nao"

    positivas = (
        "nível médio", "nivel medio", "nível difícil", "nivel dificil",
        "quero ir", "vamos para", "continuar", "aceito", "ótimo", "otimo",
        "claro", "pode", "vamos", "bora", "quero", "médio", "medio",
        "difícil", "dificil", "sim", "ok",
        "jogar de novo", "jogar novamente", "mais uma vez",
    )
    for expressao in positivas:
        if expressao in t:
            return "sim"
    return None


def interpretar_escolha_jogo(texto):
    """Retorna 'memoria', 'parentes', 'sons', 'ordem' ou None."""
    if not texto:
        return None
    t = texto.lower().strip()
    if any(x in t for x in ("parente", "família", "familia", "filho", "filha", "cadastr")):
        return "parentes"
    if any(x in t for x in ("som", "sons", "barulho", "barulhos")):
        return "sons"
    if any(
        x in t
        for x in (
            "ordem", "sequência", "sequencia", "passo", "passos",
            "etapa", "etapas", "sequencial", "ordem das coisas",
            "jogo de ordem", "ordem correta",
        )
    ):
        return "ordem"
    if any(x in t for x in ("palavra", "memor", "memória", "memoria")):
        return "memoria"
    return None


def interpretar_pronto_parentes(texto):
    if not texto:
        return False
    t = texto.lower().strip()
    return any(x in t for x in ("pronto", "começar", "comecar", "cadastrei", "pode começar", "iniciar"))


def interpretar_pedido_ajuda_som(texto):
    """Usuário não soube o som e pediu a resposta ou para pular."""
    if not texto:
        return False
    t = normalizar_texto(texto)
    frases = (
        "nao entendi",
        "nao sei",
        "qual era",
        "qual e o som",
        "qual era o som",
        "qual o som",
        "me fala",
        "fala a resposta",
        "da a resposta",
        "revela",
        "nao faco ideia",
        "pula",
        "proximo",
        "proximo som",
        "nao consegui",
        "desisto",
        "me ajuda",
        "repete a resposta",
    )
    return any(frase in t for frase in frases)


def interpretar_pedido_ajuda_ordem(texto):
    """Usuário pediu a resposta ou quer pular no jogo de ordem."""
    if not texto:
        return False
    t = normalizar_texto(texto)
    frases = (
        "nao entendi",
        "nao sei",
        "qual era",
        "qual e a ordem",
        "qual era a ordem",
        "me fala",
        "fala a resposta",
        "da a resposta",
        "revela",
        "nao faco ideia",
        "pula",
        "proximo",
        "proxima",
        "nao consegui",
        "desisto",
        "me ajuda",
        "repete a resposta",
    )
    return any(frase in t for frase in frases)


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


def registrar_estatistica(user_id, tempo_minutos, acertos=0, erros=0):
    """Registra estatísticas de uso na API do Render."""
    if not user_id or not render_disponivel():
        logging.warning(f"registrar_estatistica: user_id={user_id}, render_disponivel={render_disponivel()}")
        return False
    try:
        url = f"{RENDER_API_URL}/api/users/{user_id}/stats"
        payload = {
            "tempo": tempo_minutos,
            "correct": acertos,
            "wrong": erros
        }
        logging.info(f"registrar_estatistica: enviando para {url} - payload: {payload}")
        r = requests.post(url, headers=_headers_render(), json=payload, timeout=10)
        logging.info(f"registrar_estatistica: resposta status={r.status_code}, body={r.text}")
        if r.status_code == 200:
            return True
        logging.warning(f"Render Stats POST {r.status_code}: {r.text}")
    except Exception as e:
        logging.error(f"Erro ao registrar estatística: {e}")
    return False


def obter_link_pdf(user_id):
    """Gera link para download do PDF de estatísticas."""
    if not user_id or not render_disponivel():
        return None
    return f"{RENDER_API_URL}/api/users/{user_id}/pdf"


# Dados do jogo "Qual não pertence"
DADOS_JOGO_NAO_PERTENCE = {
    "animais": {
        "nome_tema": "animais",
        "itens": [
            {"nome": "cachorro", "imagem": "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "gato", "imagem": "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "pássaro", "imagem": "https://images.unsplash.com/photo-1444464666168-49d633b86797?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "maçã", "imagem": "https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=400&h=400&fit=crop", "pertence": False}
        ]
    },
    "frutas": {
        "nome_tema": "frutas",
        "itens": [
            {"nome": "banana", "imagem": "https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "laranja", "imagem": "https://images.unsplash.com/photo-1547514701-42782101795e?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "uva", "imagem": "https://images.unsplash.com/photo-1536304929831-ee1ca9d44906?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "carro", "imagem": "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?w=400&h=400&fit=crop", "pertence": False}
        ]
    },
    "veiculos": {
        "nome_tema": "veículos",
        "itens": [
            {"nome": "carro", "imagem": "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "bicicleta", "imagem": "https://images.unsplash.com/photo-1485965120184-e224f7a1db69?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "avião", "imagem": "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "árvore", "imagem": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=400&h=400&fit=crop", "pertence": False}
        ]
    },
    "roupas": {
        "nome_tema": "roupas",
        "itens": [
            {"nome": "camisa", "imagem": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "calça", "imagem": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "sapato", "imagem": "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "computador", "imagem": "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=400&h=400&fit=crop", "pertence": False}
        ]
    },
    "cores": {
        "nome_tema": "cores",
        "itens": [
            {"nome": "vermelho", "imagem": "https://images.unsplash.com/photo-1563089145-599997674d42?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "azul", "imagem": "https://images.unsplash.com/photo-1564349683136-77e08dba1ef7?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "amarelo", "imagem": "https://images.unsplash.com/photo-1569336415962-a4bd9f69cd83?w=400&h=400&fit=crop", "pertence": True},
            {"nome": "mesa", "imagem": "https://images.unsplash.com/photo-1530018607912-eff2daa1bac4?w=400&h=400&fit=crop", "pertence": False}
        ]
    }
}


def obter_aleatorio_jogo_nao_pertence():
    """Retorna um tema aleatório com 3 itens do tema e 1 que não pertence."""
    import random
    temas = list(DADOS_JOGO_NAO_PERTENCE.keys())
    tema_escolhido = random.choice(temas)
    dados_tema = DADOS_JOGO_NAO_PERTENCE[tema_escolhido]
    
    # Embaralhar os itens para o intruso não estar sempre na mesma posição
    itens = dados_tema["itens"].copy()
    random.shuffle(itens)
    
    return {
        "tema": dados_tema["nome_tema"],
        "itens": itens,
        "resposta_correta": [item["nome"] for item in itens if not item["pertence"]][0]
    }


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


def gerar_pergunta_parentes(people, relacoes_perguntadas=None):
    """
    Gera pergunta sobre parentes cadastrados (IA com fallback).
    Retorna dict: pergunta, relacao, nomes_esperados.
    relacoes_perguntadas: lista de relações já perguntadas para evitar repetição.
    """
    relacoes = list(people.keys())
    if not relacoes:
        return None

    # Filtra relações já perguntadas
    if relacoes_perguntadas:
        relacoes_disponiveis = [r for r in relacoes if r not in relacoes_perguntadas]
        if not relacoes_disponiveis:
            # Se todas foram perguntadas, reinicia o ciclo
            relacoes_disponiveis = relacoes
        relacoes = relacoes_disponiveis

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
    print(f"DEBUG verificar_resposta - Esperadas: {palavras_esperadas}")
    print(f"DEBUG verificar_resposta - Resposta usuário: {resposta_usuario}")
    
    if not resposta_usuario:
        print("DEBUG verificar_resposta - Resposta vazia")
        return False

    esperadas = limpar_lista_palavras(palavras_esperadas)
    ditas = extrair_palavras(resposta_usuario)
    
    print(f"DEBUG verificar_resposta - Esperadas processadas: {esperadas}")
    print(f"DEBUG verificar_resposta - Ditas processadas: {ditas}")
    
    if not esperadas or not ditas:
        print("DEBUG verificar_resposta - Listas vazias")
        return False

    # Verifica se todas as palavras esperadas estão nas ditas
    for palavra in esperadas:
        if palavra not in ditas:
            print(f"DEBUG verificar_resposta - Palavra '{palavra}' não encontrada em {ditas}")
            return False
    
    # Verifica se a quantidade de palavras bate
    resultado = len(esperadas) == len(ditas)
    print(f"DEBUG verificar_resposta - Quantidades - Esperadas: {len(esperadas)}, Ditas: {len(ditas)}, Resultado: {resultado}")
    return resultado


def verificar_nome_parente(nomes_esperados, resposta_usuario):
    """Verifica se o usuário citou os nomes esperados dos parentes."""
    print(f"DEBUG verificar_nome_parente - Nomes esperados: {nomes_esperados}")
    print(f"DEBUG verificar_nome_parente - Resposta usuário: {resposta_usuario}")
    
    if not resposta_usuario:
        print("DEBUG verificar_nome_parente - Resposta vazia")
        return False

    ditas = extrair_palavras(resposta_usuario)
    print(f"DEBUG verificar_nome_parente - Palavras ditas: {ditas}")
    
    if not ditas:
        print("DEBUG verificar_nome_parente - Lista ditas vazia")
        return False

    # Normaliza os nomes esperados para comparação
    nomes_normalizados = [normalizar_texto(nome) for nome in nomes_esperados]
    print(f"DEBUG verificar_nome_parente - Nomes normalizados: {nomes_normalizados}")
    
    # Verifica se cada nome esperado está presente exatamente na resposta
    for nome_normalizado in nomes_normalizados:
        if nome_normalizado not in ditas:
            print(f"DEBUG verificar_nome_parente - Nome '{nome_normalizado}' não encontrado em {ditas}")
            return False
    
    print("DEBUG verificar_nome_parente - Todos os nomes encontrados")
    return True


# Sons reais da biblioteca oficial Alexa Skills Kit Sound Library
SONS_DISPONIVEIS = [
    {
        "categoria": "animais",
        "nome": "cachorro",
        "audio_uri": "soundbank://soundlibrary/animals/amzn_sfx_dog_med_bark_2x_03",
        "respostas_validas": ["cachorro", "cao", "dog", "cachorro latindo"]
    },
    {
        "categoria": "animais",
        "nome": "gato",
        "audio_uri": "soundbank://soundlibrary/animals/amzn_sfx_cat_meow_1x_01",
        "respostas_validas": ["gato", "miau", "gato miando"]
    },
    {
        "categoria": "animais",
        "nome": "pássaro",
        "audio_uri": "soundbank://soundlibrary/animals/amzn_sfx_bird_chickadee_chirp_1x_01",
        "respostas_validas": ["passaro", "pássaro", "ave", "bird", "pássaro cantando"]
    },
    {
        "categoria": "ambiente",
        "nome": "campainha",
        "audio_uri": "soundbank://soundlibrary/home/amzn_sfx_doorbell_chime_01",
        "respostas_validas": ["campainha", "sino", "campainha tocando"]
    },
    {
        "categoria": "ambiente",
        "nome": "telefone",
        "audio_uri": "soundbank://soundlibrary/home/amzn_sfx_doorbell_buzz_01",
        "respostas_validas": ["telefone", "phone", "tocando"]
    },
    {
        "categoria": "ambiente",
        "nome": "porta",
        "audio_uri": "soundbank://soundlibrary/home/amzn_sfx_doorbell_01",
        "respostas_validas": ["porta", "batendo", "batida"]
    },
    {
        "categoria": "ambiente",
        "nome": "despertador",
        "audio_uri": "soundbank://soundlibrary/musical/amzn_sfx_bell_timer_01",
        "respostas_validas": ["despertador", "alarme", "relógio"]
    },
    {
        "categoria": "ambiente",
        "nome": "buzina",
        "audio_uri": "soundbank://soundlibrary/transportation/amzn_sfx_car_honk_2x_01",
        "respostas_validas": ["buzina", "carro", "horn"]
    },
]


def montar_ssml_com_som(texto_intro, audio_uri, texto_pergunta="Qual som você ouviu?"):
    """Monta resposta SSML com efeito sonoro real da biblioteca Alexa."""
    return (
        f"<speak>"
        f"{texto_intro}"
        f'<break time="0.5s"/>'
        f'<audio src="{audio_uri}"/>'
        f'<break time="1s"/>'
        f"{texto_pergunta}"
        f"</speak>"
    )


# Cenários com ordem única e inequívoca (sem passos intercambiáveis).
CENARIOS_ORDEM = [
    {
        "id": "mercado",
        "contexto": "no mercado",
        "passos": ["pegar um carrinho", "escolher os produtos", "pagar no caixa"],
    },
    {
        "id": "hospital",
        "contexto": "no hospital para uma consulta",
        "passos": ["retirar a senha", "aguardar ser chamado", "entrar no consultório"],
    },
    {
        "id": "banco",
        "contexto": "no banco",
        "passos": ["pegar a senha de atendimento", "aguardar na fila", "fazer a operação no caixa"],
    },
    {
        "id": "almoco",
        "contexto": "na hora do almoço",
        "passos": ["lavar as mãos", "sentar à mesa", "comer a comida"],
    },
    {
        "id": "cafe",
        "contexto": "para preparar um café",
        "passos": ["ferver a água", "colocar o pó no filtro", "servir na xícara"],
    },
    {
        "id": "banho",
        "contexto": "para tomar banho",
        "passos": ["ligar o chuveiro", "molhar o corpo", "ensaboar e enxaguar"],
    },
    {
        "id": "dentes",
        "contexto": "para escovar os dentes",
        "passos": ["molhar a escova", "passar a pasta de dente", "escovar os dentes"],
    },
    {
        "id": "correio",
        "contexto": "nos correios para enviar uma carta",
        "passos": ["pegar a ficha de atendimento", "esperar ser chamado", "entregar a carta no balcão"],
    },
]


def _montar_pergunta_ordem(contexto, passos_embaralhados):
    lista = (
        f"{passos_embaralhados[0]}, "
        f"{passos_embaralhados[1]} e {passos_embaralhados[2]}"
    )
    return (
        f"{contexto.capitalize()}, coloque em ordem estas três ações: {lista}. "
        f"Diga a ordem correta, do primeiro ao terceiro passo."
    )


def _extrair_passos_ia(texto):
    try:
        inicio = texto.find("{")
        fim = texto.rfind("}")
        if inicio == -1 or fim == -1:
            return None
        dados = json.loads(texto[inicio : fim + 1])
        passos = dados.get("passos") or []
        passos = [str(p).strip() for p in passos if str(p).strip()]
        if len(passos) != 3:
            return None
        contexto = str(dados.get("contexto", "")).strip() or "no dia a dia"
        return {"contexto": contexto, "passos": passos}
    except Exception as e:
        logging.error(f"Erro ao interpretar JSON de ordem: {e}")
        return None


def gerar_pergunta_ordem(cenarios_ja_perguntados=None):
    """
    Gera pergunta sobre ordem de passos (IA com fallback curado).
    Retorna dict: pergunta, passos, contexto, id.
    """
    if cenarios_ja_perguntados is None:
        cenarios_ja_perguntados = []

    disponiveis = [c for c in CENARIOS_ORDEM if c["id"] not in cenarios_ja_perguntados]
    if not disponiveis:
        disponiveis = CENARIOS_ORDEM

    base = random.choice(disponiveis)
    contexto = base["contexto"]
    passos = list(base["passos"])

    try:
        prompt = f"""
        Crie um exercício de memória sequencial para idosos em português do Brasil.
        Contexto sugerido: {contexto}.
        Use como inspiração estes passos na ordem correta: {", ".join(passos)}.

        Regras OBRIGATÓRIAS:
        - Exatamente 3 passos curtos e claros
        - Apenas UMA ordem lógica possível (sequência temporal, sem ambiguidade)
        - Situação cotidiana simples
        - Não use passos que possam ser trocados sem problema
        - Cada passo deve ter no máximo 8 palavras

        Responda SOMENTE com JSON válido neste formato:
        {{"contexto": "no mercado", "passos": ["primeiro passo", "segundo passo", "terceiro passo"]}}
        """
        texto = _chamar_openrouter(prompt)
        gerado = _extrair_passos_ia(texto)
        if gerado:
            contexto = gerado["contexto"]
            passos = gerado["passos"]
    except Exception as e:
        logging.error(f"Erro ao gerar pergunta de ordem: {e}")

    embaralhados = passos[:]
    random.shuffle(embaralhados)
    if embaralhados == passos:
        embaralhados = passos[::-1]

    return {
        "id": base["id"],
        "contexto": contexto,
        "passos": passos,
        "pergunta": _montar_pergunta_ordem(contexto, embaralhados),
    }


def _palavras_chave_passo(passo):
    palavras = [p for p in extrair_palavras(passo) if len(p) > 2]
    stopwords = {
        "para", "com", "sem", "uma", "uns", "umas", "seu", "sua", "seus", "suas",
        "que", "por", "dos", "das", "nos", "nas", "pelo", "pela",
    }
    return [p for p in palavras if p not in stopwords] or palavras


def verificar_resposta_ordem(passos_corretos, resposta_usuario):
    """Verifica se o usuário disse os passos na ordem correta."""
    if not resposta_usuario or not passos_corretos:
        return False

    resposta_norm = normalizar_texto(resposta_usuario)
    if not resposta_norm:
        return False

    ultima_pos = -1
    for passo in passos_corretos:
        chaves = _palavras_chave_passo(passo)
        encontrou = False
        melhor_pos = None

        for chave in chaves:
            pos = resposta_norm.find(chave)
            if pos != -1 and pos > ultima_pos:
                if melhor_pos is None or pos < melhor_pos:
                    melhor_pos = pos
                    encontrou = True

        if not encontrou:
            passo_norm = normalizar_texto(passo)
            pos = resposta_norm.find(passo_norm)
            if pos != -1 and pos > ultima_pos:
                melhor_pos = pos
                encontrou = True

        if not encontrou:
            return False

        ultima_pos = melhor_pos

    return True


def formatar_ordem_correta(passos):
    partes = []
    ordinais = ("Primeiro", "Depois", "Por último")
    for i, passo in enumerate(passos):
        if i < len(ordinais):
            partes.append(f"{ordinais[i]}, {passo}")
        else:
            partes.append(passo)
    return ". ".join(partes)


def gerar_pergunta_som(sons_ja_perguntados=None):
    """
    Gera uma pergunta de reconhecimento de som.
    Retorna dict: audio_uri, nome, respostas_validas, categoria.
    """
    if sons_ja_perguntados is None:
        sons_ja_perguntados = []

    # Filtra sons já perguntados
    sons_disponiveis = [s for s in SONS_DISPONIVEIS if s["nome"] not in sons_ja_perguntados]

    if not sons_disponiveis:
        # Se todos foram perguntados, reinicia
        sons_disponiveis = SONS_DISPONIVEIS

    som_escolhido = random.choice(sons_disponiveis)

    return {
        "audio_uri": som_escolhido["audio_uri"],
        "nome": som_escolhido["nome"],
        "respostas_validas": som_escolhido["respostas_validas"],
        "categoria": som_escolhido["categoria"]
    }


def extrair_texto_do_evento_raw(handler_input):
    """Lê o texto falado diretamente do JSON do evento Alexa (camelCase)."""
    try:
        envelope = handler_input.request_envelope
        if hasattr(envelope, "to_dict"):
            event = envelope.to_dict()
        else:
            return ""

        req = event.get("request") or {}
        transcript = req.get("inputTranscript") or req.get("input_transcript")
        if transcript:
            return str(transcript).strip()

        intent = req.get("intent") or {}
        for slot in (intent.get("slots") or {}).values():
            if not slot:
                continue
            valor = slot.get("value")
            if valor:
                return str(valor).strip()
            resolutions = (slot.get("resolutions") or {}).get("resolutionsPerAuthority") or []
            for authority in resolutions:
                for item in authority.get("values") or []:
                    nome = (item.get("value") or {}).get("name")
                    if nome:
                        return str(nome).strip()
    except Exception as e:
        logger.warning("Falha ao extrair texto do evento raw: %s", e)
    return ""


def extrair_texto_usuario_alexa(handler_input):
    """Extrai o que o usuário falou, tentando todas as fontes disponíveis."""
    import ask_sdk_core.utils as ask_utils

    request = handler_input.request_envelope.request

    if hasattr(request, "input_transcript") and request.input_transcript:
        return request.input_transcript.strip()

    for slot_name in ("som", "resposta"):
        valor = ask_utils.get_slot_value(handler_input=handler_input, slot_name=slot_name) or ""
        if valor:
            return valor.strip()

    if hasattr(request, "intent") and request.intent and request.intent.slots:
        for slot in request.intent.slots.values():
            if slot and slot.value:
                return slot.value.strip()
            resolutions = getattr(slot, "resolutions", None)
            if not resolutions:
                continue
            for authority in resolutions.resolutions_per_authority or []:
                for resolution in authority.values or []:
                    name = getattr(getattr(resolution, "value", None), "name", None)
                    if name:
                        return name.strip()

    return extrair_texto_do_evento_raw(handler_input)


def verificar_resposta_som(respostas_validas, resposta_usuario, nome_som=None):
    """Verifica se o usuário reconheceu o som corretamente."""
    if not resposta_usuario:
        return False

    resposta_normalizada = normalizar_texto(resposta_usuario)
    palavras_ditas = set(extrair_palavras(resposta_usuario))

    termos_validos = [normalizar_texto(r) for r in respostas_validas]
    if nome_som:
        termos_validos.append(normalizar_texto(nome_som))

    for termo in termos_validos:
        if not termo:
            continue
        if termo in resposta_normalizada or resposta_normalizada in termo:
            return True
        if termo in palavras_ditas:
            return True

    return False

