"""
Funções auxiliares para renderizar interfaces APL no Echo Show.
"""
import json
import os
from ask_sdk_model import (
    Response,
    ui
)
from ask_sdk_model.ui import (
    DisplayInterface,
    RenderDocumentDirective
)


def carregar_documento_apl(nome_arquivo="main.json"):
    """Carrega documento APL do arquivo JSON."""
    caminho = os.path.join(os.path.dirname(__file__), "..", "apl", nome_arquivo)
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar APL: {e}")
        return None


def criar_resposta_apl(handler_input, documento_apl, dados_template, token="token"):
    """Cria resposta com diretiva APL."""
    if not handler_input.request_envelope.context:
        return None
    
    display_interface = handler_input.request_envelope.context.display
    if not display_interface:
        return None
    
    try:
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


def tem_suporte_apl(handler_input):
    """Verifica se o dispositivo suporta APL (Echo Show)."""
    if not handler_input.request_envelope.context:
        return False
    
    display_interface = handler_input.request_envelope.context.display
    return display_interface is not None
