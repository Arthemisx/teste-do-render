"""
Funções auxiliares para renderizar interfaces APL no Echo Show.
"""
import json
import os
from ask_sdk_model import Response
from ask_sdk_model.interfaces.alexa.presentation.apl import (
    RenderDocumentDirective
)


def carregar_documento_apl(nome_arquivo="main.json"):
    """Carrega documento APL do arquivo JSON."""
    caminho = os.path.join(os.path.dirname(__file__), "..", "apl", nome_arquivo)
    print(f"APL: Tentando carregar arquivo de {caminho}")
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"APL: Arquivo carregado com sucesso, tipo={data.get('type')}, versão={data.get('version')}")
            return data
    except Exception as e:
        print(f"Erro ao carregar APL: {e}")
        import traceback
        traceback.print_exc()
        return None


def criar_resposta_apl(handler_input, documento_apl, dados_template, token="token"):
    """Cria resposta com diretiva APL."""
    if not handler_input.request_envelope.context:
        print("APL: Contexto não disponível")
        return None
    
    # Não verifica display_interface pois viewports são suficientes para APL
    try:
        print(f"APL: Enviando documento com token={token}, dados={dados_template}")
        return (
            handler_input.response_builder
            .add_directive(
                RenderDocumentDirective(
                    token=token,
                    document=documento_apl,
                    datas=dados_template
                )
            )
        )
    except Exception as e:
        print(f"Erro ao criar resposta APL: {e}")
        import traceback
        traceback.print_exc()
        return None


def mostrar_tela_principal(handler_input):
    """Mostra tela principal da skill no Echo Show."""
    documento_apl = carregar_documento_apl()
    if not documento_apl:
        return None
    
    dados_template = {
        "mainScreenData": {
            "title": "Dona Memória",
            "subtitle": "Sua skill Alexa para exercícios de memória",
            "description": "Olá! Eu sou a Dona Memória, sua assistente para exercícios cognitivos.\n\nAjudo você a treinar a memória com jogos divertidos envolvendo:\n\n• Lembrar de familiares\n• Identificar sons\n• Memorizar sequências\n\nPeça à Alexa: Abrir Dona Memória",
            "showStatsButton": True
        }
    }
    
    return criar_resposta_apl(handler_input, documento_apl, dados_template, "mainScreen")


def mostrar_tela_estatisticas(handler_input, dados_estatisticas):
    """Mostra tela de estatísticas no Echo Show."""
    documento_apl = carregar_documento_apl()
    if not documento_apl:
        return None
    
    # Formatar dados para APL
    daily_stats = []
    for stat in dados_estatisticas.get("dailyStats", []):
        daily_stats.append({
            "date": stat.get("date", ""),
            "time": stat.get("time", 0),
            "correct": stat.get("correct", 0),
            "wrong": stat.get("wrong", 0)
        })
    
    dados_template = {
        "statsScreenData": {
            "totalTime": dados_estatisticas.get("totalTime", 0),
            "dailyStats": daily_stats
        }
    }
    
    return criar_resposta_apl(handler_input, documento_apl, dados_template, "statsScreen")


def mostrar_tela_jogo_nao_pertence(handler_input, tema, itens):
    """Mostra tela do jogo 'Qual não pertence' no Echo Show."""
    documento_apl = carregar_documento_apl()
    if not documento_apl:
        return None
    
    dados_template = {
        "jogoNaoPertenceData": {
            "tema": tema,
            "itens": itens
        }
    }
    
    return criar_resposta_apl(handler_input, documento_apl, dados_template, "jogoNaoPertenceScreen")


def tem_suporte_apl(handler_input):
    """Verifica se o dispositivo suporta APL (Echo Show)."""
    if not handler_input.request_envelope.context:
        return False
    
    # Verifica se há display ou viewports
    display_interface = handler_input.request_envelope.context.display
    if display_interface:
        return True
    
    # Verifica se há Viewports (indicativo de dispositivo com tela)
    context = handler_input.request_envelope.context
    if hasattr(context, 'viewports') and context.viewports:
        return True
    
    return False
