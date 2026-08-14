"""
Funções auxiliares para renderizar interfaces APL no Echo Show.
"""
import json
import os
import logging
from ask_sdk_model import Response
from ask_sdk_model.interfaces.alexa.presentation.apl import (
    RenderDocumentDirective
)

logger = logging.getLogger(__name__)


def carregar_documento_apl(nome_arquivo="main.json"):
    """Carrega documento APL do arquivo JSON."""
    caminho = os.path.join(os.path.dirname(__file__), "..", "apl", nome_arquivo)
    logger.info(f"APL: Tentando carregar arquivo de {caminho}")
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"APL: Arquivo carregado com sucesso, tipo={data.get('type')}, versão={data.get('version')}")
            return data
    except Exception as e:
        logger.error(f"Erro ao carregar APL: {e}")
        import traceback
        traceback.print_exc()
        return None


def criar_resposta_apl(handler_input, documento_apl, dados_template, token="token"):
    """Cria resposta com diretiva APL."""
    logger.info(f"criar_resposta_apl - iniciando com token={token}")
    
    if not handler_input.request_envelope.context:
        logger.warning("APL: Contexto não disponível")
        return None
    
    try:
        logger.info(f"APL: Enviando documento com token={token}")
        # Usar sintaxe simplificada sem parâmetro data para compatibilidade
        resultado = (
            handler_input.response_builder
            .add_directive(
                RenderDocumentDirective(
                    token=token,
                    document=documento_apl
                )
            )
        )
        logger.info("APL: Diretiva adicionada com sucesso")
        return resultado
    except Exception as e:
        logger.error(f"Erro ao criar resposta APL: {e}")
        import traceback
        traceback.print_exc()
        return None


def mostrar_tela_principal(handler_input):
    """Mostra tela principal da skill no Echo Show."""
    logger.info("mostrar_tela_principal - iniciando")
    
    # Criar documento APL com dados embutidos para evitar problemas de parâmetros
    documento_apl = {
        "type": "APL",
        "version": "1.7",
        "theme": "dark",
        "import": [
            {
                "name": "alexa-layouts",
                "version": "1.4.0"
            }
        ],
        "mainTemplate": {
            "parameters": [],
            "items": [
                {
                    "type": "Container",
                    "width": "100%",
                    "height": "100%",
                    "backgroundColor": "#FFFACD",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "items": [
                        {
                            "type": "Text",
                            "text": "Dona Memória",
                            "fontSize": "48dp",
                            "fontWeight": "bold",
                            "color": "#FF69B4",
                            "textAlign": "center"
                        },
                        {
                            "type": "Text",
                            "text": "Sua skill Alexa para exercícios de memória",
                            "fontSize": "28dp",
                            "color": "#000000",
                            "textAlign": "center",
                            "marginTop": "20dp"
                        }
                    ]
                }
            ]
        }
    }
    
    logger.info(f"mostrar_tela_principal - documento APL criado inline com dados embutidos")
    return criar_resposta_apl(handler_input, documento_apl, {}, "mainScreen")


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
