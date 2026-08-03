# -*- coding: utf-8 -*-

# This sample demonstrates handling intents from an Alexa skill using the Alexa Skills Kit SDK for Python.
# Please visit https://alexa.design/cookbook for additional examples on implementing slots, dialog management,
# session persistence, api calls, and more.
# This sample is built using the handler classes approach in skill builder.

# -*- coding: utf-8 -*-

import logging
import ask_sdk_core.utils as ask_utils

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model import Response
from ask_sdk_model.ui import SimpleCard

from utils import (
    adicionar_parente,
    carregar_dados_usuario,
    extrair_texto_usuario_alexa,
    extrair_texto_do_evento_raw,
    formatar_ordem_correta,
    formatar_parentes_cadastrados,
    gerar_palavras_aleatorias,
    gerar_pergunta_ordem,
    gerar_pergunta_parentes,
    gerar_pergunta_som,
    interpretar_confirmacao,
    interpretar_escolha_jogo,
    interpretar_pedido_ajuda_ordem,
    interpretar_pedido_ajuda_som,
    interpretar_pronto_parentes,
    montar_ssml_com_som,
    normalizar_texto,
    obter_aleatorio_jogo_nao_pertence,
    obter_link_pdf,
    registrar_estatistica,
    render_disponivel,
    salvar_dados_usuario,
    verificar_nome_parente,
    verificar_resposta,
    verificar_resposta_ordem,
    verificar_resposta_som,
)

from apl_utils import (
    mostrar_tela_jogo_nao_pertence,
    mostrar_tela_principal,
    mostrar_tela_estatisticas,
    tem_suporte_apl,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def obter_user_id(handler_input):
    try:
        return handler_input.request_envelope.session.user.user_id
    except Exception:
        return None


def sincronizar_dados_nuvem(handler_input, session):
    """Carrega parentes e progresso salvos no Render para esta sessão."""
    user_id = obter_user_id(handler_input)
    if not user_id:
        return
    session["user_id"] = user_id
    dados = carregar_dados_usuario(user_id)
    # Só sobrescreve se não existir na sessão (preserva dados modificados)
    if "people" not in session:
        session["people"] = dados.get("people", {})
    if "memoria_salva" not in session:
        session["memoria_salva"] = dados.get("memoria", {})


def salvar_na_nuvem(session):
    """Persiste dados atuais no Render."""
    user_id = session.get("user_id")
    if not user_id:
        return
    payload = {
        "people": session.get("people", {}),
        "memoria": session.get("memoria_salva", {}),
    }
    salvar_dados_usuario(user_id, payload)


def obter_texto_usuario(handler_input):
    texto = extrair_texto_usuario_alexa(handler_input)
    if texto:
        return texto

    person_name = ask_utils.get_slot_value(handler_input=handler_input, slot_name="personName") or ""
    relation = ask_utils.get_slot_value(handler_input=handler_input, slot_name="relation") or ""
    if person_name and relation:
        return f"{person_name} {relation}"

    return ""


def iniciar_jogo_memoria(session_attrs):
    palavras = gerar_palavras_aleatorias(3)
    session_attrs["modo_jogo"] = "memoria"
    session_attrs["jogo_ativo"] = True
    session_attrs["parentes_ativo"] = False
    session_attrs["ordem_ativo"] = False
    session_attrs["aguardando_escolha_jogo"] = False
    session_attrs["nivel"] = "facil"
    session_attrs["palavras"] = palavras
    session_attrs["rodada"] = 1
    session_attrs["aguardando_confirmacao_nivel"] = False
    session_attrs["aguardando_novo_jogo"] = False
    return (
        f"Vamos jogar memorizar palavras no nível fácil! "
        f"Lembre-se das palavras: {', '.join(palavras)}. Agora, repita as palavras!"
    )


def iniciar_turno_som(session_attrs, prefixo=""):
    """Inicia um único som para o usuário adivinhar."""
    if "sons_perguntados" not in session_attrs:
        session_attrs["sons_perguntados"] = []

    from utils import SONS_DISPONIVEIS
    if len(session_attrs["sons_perguntados"]) >= len(SONS_DISPONIVEIS):
        session_attrs["sons_perguntados"] = []

    som = gerar_pergunta_som(session_attrs["sons_perguntados"])
    session_attrs["som_atual"] = som
    session_attrs["aguardando_novo_jogo_sons"] = False

    intro = f"{prefixo}Escute com atenção. "
    return montar_ssml_com_som(intro, som["audio_uri"])


def iniciar_jogo_sons(session_attrs, prefixo=""):
    session_attrs["modo_jogo"] = "sons"
    session_attrs["sons_ativo"] = True
    session_attrs["ordem_ativo"] = False
    session_attrs["jogo_ativo"] = False
    session_attrs["aguardando_escolha_jogo"] = False
    session_attrs["aguardando_novo_jogo_sons"] = False
    session_attrs["sons_perguntados"] = []

    return iniciar_turno_som(session_attrs, f"{prefixo}Vamos jogar reconhecer sons! ")


def iniciar_turno_ordem(session_attrs, prefixo=""):
    """Inicia uma pergunta de ordem de passos."""
    if "ordens_perguntadas" not in session_attrs:
        session_attrs["ordens_perguntadas"] = []

    pergunta = gerar_pergunta_ordem(session_attrs["ordens_perguntadas"])
    session_attrs["ordem_atual"] = pergunta
    session_attrs["aguardando_novo_jogo_ordem"] = False

    intro = f"{prefixo}" if prefixo else ""
    return f"{intro}{pergunta['pergunta']}"


def iniciar_jogo_ordem(session_attrs, prefixo=""):
    session_attrs["modo_jogo"] = "ordem"
    session_attrs["ordem_ativo"] = True
    session_attrs["sons_ativo"] = False
    session_attrs["jogo_ativo"] = False
    session_attrs["parentes_ativo"] = False
    session_attrs["aguardando_escolha_jogo"] = False
    session_attrs["aguardando_novo_jogo_ordem"] = False
    session_attrs["ordens_perguntadas"] = []

    return iniciar_turno_ordem(
        session_attrs,
        f"{prefixo}Vamos jogar ordem das coisas! ",
    )


def iniciar_modo_parentes(session_attrs, prefixo=""):
    session_attrs["modo_jogo"] = "parentes"
    session_attrs["parentes_ativo"] = True
    session_attrs["jogo_ativo"] = False
    session_attrs["ordem_ativo"] = False
    session_attrs["aguardando_escolha_jogo"] = False
    session_attrs["relacoes_perguntadas"] = []  # Reseta rastreamento
    people = session_attrs.get("people", {})

    if not people:
        session_attrs["parentes_fase"] = "cadastro"
        return (
            f"{prefixo}"
            "Vamos treinar a memória sobre sua família! "
            "Primeiro cadastre parentes. Diga por exemplo: João é meu filho. "
            "Quando terminar, diga pronto para começar as perguntas."
        )

    session_attrs["parentes_fase"] = "pergunta"
    pergunta = gerar_pergunta_parentes(people)
    session_attrs["pergunta_atual"] = pergunta
    resumo = formatar_parentes_cadastrados(people)
    return (
        f"{prefixo}"
        f"Encontrei seus parentes cadastrados: {resumo}. "
        f"Vamos começar! {pergunta['pergunta']}"
    )


class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        import time
        session = handler_input.attributes_manager.session_attributes
        sincronizar_dados_nuvem(handler_input, session)
        
        # Rastrear tempo de início da sessão
        session["session_start_time"] = time.time()
        session["session_acertos"] = 0
        session["session_erros"] = 0
        
        session["aguardando_escolha_jogo"] = True
        session["jogo_ativo"] = False
        session["parentes_ativo"] = False

        extra = ""
        if session.get("people"):
            extra = "Bom te ver de novo! Seus parentes continuam cadastrados. "

        speak_output = (
            f"Olá, eu sou a Dona Memória! {extra}"
            "Você pode jogar memorizar palavras, o jogo de parentes, o jogo de sons "
            "ou o jogo de ordem das coisas. Você também pode acessar suas configurações "
            "para ver suas estatísticas de uso. O que você quer fazer?"
        )
        
        response_builder = handler_input.response_builder.speak(speak_output).ask(
            "Diga memorizar palavras, jogo de parentes, jogo de sons, jogo de ordem ou acessar configurações."
        )
        
        # Mostrar interface APL se disponível
        logger.info(f"Verificando suporte APL...")
        if tem_suporte_apl(handler_input):
            logger.info(f"APL suportado, tentando mostrar tela principal...")
            resposta_apl = mostrar_tela_principal(handler_input)
            if resposta_apl:
                logger.info(f"Resposta APL criada com sucesso")
                response_builder = resposta_apl
            else:
                logger.warning(f"Resposta APL é None")
        else:
            logger.warning(f"APL não suportado neste dispositivo")
        
        return response_builder.response


class MenuJogoHandler(AbstractRequestHandler):
    """Menu: escolher entre memorizar palavras, parentes, sons ou ordem."""

    def can_handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        texto = obter_texto_usuario(handler_input).lower()
        logger.info(f"MenuJogoHandler - texto recebido: '{texto}'")
        
        # Não responder se usuário pediu configurações ou exportação de PDF
        if any(palavra in texto for palavra in ["configurações", "configuracao", "estatísticas", "estatisticas"]):
            logger.info(f"MenuJogoHandler - detectou configurações, retornando False")
            return False
        if any(palavra in texto for palavra in ["exportar", "pdf", "relatório", "relatorio", "baixar"]):
            logger.info(f"MenuJogoHandler - detectou exportação PDF, retornando False")
            return False
        
        return (
            ask_utils.is_intent_name("QueroJogarIntent")(handler_input)
            or ask_utils.is_intent_name("EscolherMemoriaIntent")(handler_input)
            or ask_utils.is_intent_name("EscolherParentesIntent")(handler_input)
            or ask_utils.is_intent_name("EscolherSonsIntent")(handler_input)
            or ask_utils.is_intent_name("EscolherOrdemIntent")(handler_input)
            or session.get("aguardando_escolha_jogo", False)
        )

    def handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes

        if ask_utils.is_intent_name("EscolherMemoriaIntent")(handler_input):
            speak_output = iniciar_jogo_memoria(session)
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask("Repita as palavras que eu disse.")
                .response
            )

        if ask_utils.is_intent_name("EscolherParentesIntent")(handler_input):
            sincronizar_dados_nuvem(handler_input, session)
            speak_output = iniciar_modo_parentes(session)
            pergunta_follow = (
                "Cadastre um parente, por exemplo Maria é minha filha."
                if session.get("parentes_fase") == "cadastro"
                else "Qual é a sua resposta?"
            )
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask(pergunta_follow)
                .response
            )

        if ask_utils.is_intent_name("EscolherSonsIntent")(handler_input):
            speak_output = iniciar_jogo_sons(session)
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask("Diga quais sons você ouviu.")
                .response
            )

        if ask_utils.is_intent_name("EscolherOrdemIntent")(handler_input):
            speak_output = iniciar_jogo_ordem(session)
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask("Qual é a ordem correta?")
                .response
            )

        escolha = interpretar_escolha_jogo(obter_texto_usuario(handler_input))
        if escolha == "memoria":
            speak_output = iniciar_jogo_memoria(session)
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask("Repita as palavras que eu disse.")
                .response
            )
        if escolha == "parentes":
            sincronizar_dados_nuvem(handler_input, session)
            speak_output = iniciar_modo_parentes(session)
            follow = (
                "Cadastre um parente, por exemplo João é meu filho."
                if session.get("parentes_fase") == "cadastro"
                else "Qual é a sua resposta?"
            )
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask(follow)
                .response
            )
        if escolha == "sons":
            speak_output = iniciar_jogo_sons(session)
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask("Diga quais sons você ouviu.")
                .response
            )
        if escolha == "ordem":
            speak_output = iniciar_jogo_ordem(session)
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask("Qual é a ordem correta?")
                .response
            )

        session["aguardando_escolha_jogo"] = True
        speak_output = (
            "Temos quatro jogos: memorizar palavras, jogo de parentes, jogo de sons "
            "e jogo de ordem das coisas. Qual você quer? "
            "Diga memorizar palavras, jogo de parentes, jogo de sons ou jogo de ordem."
        )
        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask("Memorizar palavras, parentes, sons ou ordem?")
            .response
        )


class JogoParentesHandler(AbstractRequestHandler):
    """Cadastro de parentes + perguntas com IA."""

    def can_handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        return (
            session.get("parentes_ativo", False)
            or ask_utils.is_intent_name("RegisterPersonRelationIntent")(handler_input)
            or ask_utils.is_intent_name("ProntoParentesIntent")(handler_input)
        )

    def handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        sincronizar_dados_nuvem(handler_input, session)
        session["parentes_ativo"] = True
        session["modo_jogo"] = "parentes"

        # Responder pergunta (prioridade sobre cadastro durante fase de perguntas)
        if session.get("parentes_fase") == "pergunta" and session.get("pergunta_atual"):
            resposta = obter_texto_usuario(handler_input)
            pergunta = session["pergunta_atual"]
            nomes = pergunta["nomes_esperados"]
            acertou = verificar_nome_parente(nomes, resposta)

            # Inicializa rastreamento de relações perguntadas
            if "relacoes_perguntadas" not in session:
                session["relacoes_perguntadas"] = []
            relacao_atual = pergunta["relacao"]
            if relacao_atual not in session["relacoes_perguntadas"]:
                session["relacoes_perguntadas"].append(relacao_atual)

            # Verifica se há mais relações para perguntar
            total_relacoes = list(session["people"].keys())
            relacoes_restantes = [r for r in total_relacoes if r not in session["relacoes_perguntadas"]]

            if acertou:
                # Registrar acerto nas estatísticas da sessão
                session["session_acertos"] = session.get("session_acertos", 0) + 1
                
                if not relacoes_restantes:
                    # Acertou e não há mais relações - finalizar jogo
                    session["parentes_ativo"] = False
                    session["parentes_fase"] = None
                    session["pergunta_atual"] = None
                    session["relacoes_perguntadas"] = []
                    session["aguardando_escolha_jogo"] = True
                    speak_output = (
                        f"Parabéns! Você respondeu sobre todos os seus parentes cadastrados. "
                        f"Quer cadastrar mais parentes ou jogar outro jogo?"
                    )
                    return (
                        handler_input.response_builder
                        .speak(speak_output)
                        .ask("Diga cadastrar mais parentes, memorizar palavras ou sair.")
                        .response
                    )
                
                # Acertou e há mais relações - próxima pergunta
                proxima = gerar_pergunta_parentes(session["people"], session["relacoes_perguntadas"])
                session["pergunta_atual"] = proxima
                speak_output = (
                    f"Muito bem, você acertou! Próxima pergunta: {proxima['pergunta']}"
                )
                return (
                    handler_input.response_builder
                    .speak(speak_output)
                    .ask("Qual é a sua resposta?")
                    .response
                )
            else:
                # Registrar erro nas estatísticas da sessão
                session["session_erros"] = session.get("session_erros", 0) + 1
                
                # Errou - mostra resposta correta e repete a mesma pergunta
                nomes_txt = " e ".join(nomes)
                speak_output = (
                    f"Quase! O correto era {nomes_txt}. "
                    f"Vamos tentar de novo: {pergunta['pergunta']}"
                )
                return (
                    handler_input.response_builder
                    .speak(speak_output)
                    .ask("Qual é a sua resposta?")
                    .response
                )

        # Cadastrar parente (só se não estiver em fase de perguntas)
        if ask_utils.is_intent_name("RegisterPersonRelationIntent")(handler_input):
            person_name = ask_utils.get_slot_value(handler_input, "personName")
            relation = ask_utils.get_slot_value(handler_input, "relation")
            if not person_name or not relation:
                speak_output = "Não entendi. Diga por exemplo: Maria é minha filha."
                return (
                    handler_input.response_builder
                    .speak(speak_output)
                    .ask("Pode repetir o nome e a relação?")
                    .response
                )
            if "people" not in session:
                session["people"] = {}
            adicionar_parente(session["people"], relation, person_name)
            salvar_na_nuvem(session)
            msg_salvo = " Salvei na sua memória permanente." if render_disponivel() else ""
            speak_output = (
                f"Registrei {person_name} como seu {relation}.{msg_salvo} "
                f"Cadastre mais alguém ou diga pronto para começar as perguntas."
            )
            session["parentes_fase"] = "cadastro"
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask("Quer cadastrar mais alguém?")
                .response
            )

        # Terminar cadastro e começar perguntas
        if (
            ask_utils.is_intent_name("ProntoParentesIntent")(handler_input)
            or interpretar_pronto_parentes(obter_texto_usuario(handler_input))
        ):
            if not session.get("people"):
                speak_output = "Você ainda não cadastrou ninguém. Diga por exemplo: Ana é minha mãe."
                return (
                    handler_input.response_builder
                    .speak(speak_output)
                    .ask("Cadastre um parente.")
                    .response
                )
            pergunta = gerar_pergunta_parentes(session["people"])
            session["parentes_fase"] = "pergunta"
            session["pergunta_atual"] = pergunta
            return (
                handler_input.response_builder
                .speak(pergunta["pergunta"])
                .ask("Qual é a sua resposta?")
                .response
            )

        # Fase cadastro (fallback)
        speak_output = (
            "Cadastre parentes dizendo por exemplo Pedro é meu filho. "
            "Quando terminar, diga pronto para começar."
        )
        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask("Cadastre um parente ou diga pronto.")
            .response
        )


class JogoSonsHandler(AbstractRequestHandler):
    """Jogo de reconhecimento de sons."""

    _INTENTS_MENU = (
        "QueroJogarIntent",
        "EscolherMemoriaIntent",
        "EscolherParentesIntent",
        "EscolherSonsIntent",
        "EscolherOrdemIntent",
    )

    def can_handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        intent = ask_utils.get_intent_name(handler_input)

        if intent in self._INTENTS_MENU:
            if intent == "EscolherSonsIntent" and session.get("aguardando_novo_jogo_sons"):
                return True
            return False

        if session.get("sons_ativo", False) or session.get("aguardando_novo_jogo_sons", False):
            return True

        return intent == "ResponderSonsIntent"

    def _texto_confirmacao(self, handler_input):
        texto = obter_texto_usuario(handler_input)
        if not texto:
            texto = extrair_texto_do_evento_raw(handler_input) or ""
        return texto.strip()

    def _usuario_confirmou_sim(self, handler_input):
        intent = ask_utils.get_intent_name(handler_input)
        if intent in ("AMAZON.YesIntent", "ConfirmarNivelIntent"):
            return True
        if ask_utils.is_intent_name("EscolherSonsIntent")(handler_input):
            return True
        texto = self._texto_confirmacao(handler_input)
        if interpretar_escolha_jogo(texto) == "sons":
            return True
        return interpretar_confirmacao(texto) == "sim"

    def _usuario_confirmou_nao(self, handler_input):
        intent = ask_utils.get_intent_name(handler_input)
        if intent in ("AMAZON.NoIntent", "RecusarIntent"):
            return True
        texto = self._texto_confirmacao(handler_input)
        if interpretar_confirmacao(texto) == "nao":
            return True
        t = normalizar_texto(texto)
        return t in ("nao", "n", "no")

    def handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        session["sons_ativo"] = True
        session["modo_jogo"] = "sons"

        if session.get("aguardando_novo_jogo_sons"):
            intent = ask_utils.get_intent_name(handler_input)
            logger.info(
                "Jogo sons confirmação - intent=%s, texto='%s'",
                intent,
                self._texto_confirmacao(handler_input),
            )
            if self._usuario_confirmou_sim(handler_input):
                speak_output = iniciar_turno_som(session, "Ótimo! ")
                return (
                    handler_input.response_builder
                    .speak(speak_output)
                    .ask("Qual som você ouviu?")
                    .response
                )
            if self._usuario_confirmou_nao(handler_input):
                session["sons_ativo"] = False
                session["aguardando_novo_jogo_sons"] = False
                session["som_atual"] = None
                session["aguardando_escolha_jogo"] = True
                return (
                    handler_input.response_builder
                    .speak(
                        "Tudo bem! Quer jogar memorizar palavras, jogo de parentes "
                        "ou diga sair para encerrar."
                    )
                    .ask("O que você quer fazer?")
                    .response
                )
            return (
                handler_input.response_builder
                .speak("Não entendi. Diga sim para jogar de novo ou não para sair.")
                .ask("Sim ou não?")
                .response
            )

        # Verificar resposta do usuário
        if session.get("som_atual"):
            resposta = obter_texto_usuario(handler_input)
            if not resposta:
                resposta = extrair_texto_do_evento_raw(handler_input) or ""

            som_atual = session["som_atual"]
            respostas_validas = som_atual["respostas_validas"]
            pediu_ajuda = (
                ask_utils.is_intent_name("NaoEntendiSonsIntent")(handler_input)
                or interpretar_pedido_ajuda_som(resposta)
            )

            if not resposta and not pediu_ajuda:
                intent_name = ask_utils.get_intent_name(handler_input)
                logger.warning(
                    "Jogo sons - resposta vazia, intent=%s, som=%s, evento=%s",
                    intent_name,
                    som_atual.get("nome"),
                    extrair_texto_do_evento_raw(handler_input) or "(vazio)",
                )
                speak_output = montar_ssml_com_som(
                    "Não consegui entender. Escute de novo: ",
                    som_atual["audio_uri"],
                )
                return (
                    handler_input.response_builder
                    .speak(speak_output)
                    .ask("Qual som você ouviu?")
                    .response
                )

            acertou = (
                False
                if pediu_ajuda
                else verificar_resposta_som(
                    respostas_validas, resposta, som_atual.get("nome")
                )
            )
            logger.info(
                "Jogo sons - resposta='%s', som='%s', acertou=%s, pediu_ajuda=%s",
                resposta, som_atual.get("nome"), acertou, pediu_ajuda,
            )

            # Rastrear sons já perguntados
            if "sons_perguntados" not in session:
                session["sons_perguntados"] = []
            if som_atual["nome"] not in session["sons_perguntados"]:
                session["sons_perguntados"].append(som_atual["nome"])

            session["som_atual"] = None
            session["aguardando_novo_jogo_sons"] = True

            if acertou:
                # Registrar acerto nas estatísticas da sessão
                session["session_acertos"] = session.get("session_acertos", 0) + 1
                feedback = f"Muito bem, você acertou! Era {som_atual['nome']}."
            elif pediu_ajuda:
                # Não conta como erro quando pediu ajuda
                feedback = f"Sem problema! Esse som era {som_atual['nome']}."
            else:
                # Registrar erro nas estatísticas da sessão
                session["session_erros"] = session.get("session_erros", 0) + 1
                feedback = f"Quase! Era {som_atual['nome']}."

            speak_output = (
                f"{feedback} Quer jogar de novo ou sair? "
                f"Diga sim para jogar ou não para sair."
            )
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask("Sim para jogar de novo, ou não para sair.")
                .response
            )

        return (
            handler_input.response_builder
            .speak("Desculpe, ocorreu um erro no jogo de sons.")
            .ask("Quer tentar de novo?")
            .response
        )


class JogoOrdemHandler(AbstractRequestHandler):
    """Jogo de ordem de passos do dia a dia."""

    _INTENTS_MENU = (
        "QueroJogarIntent",
        "EscolherMemoriaIntent",
        "EscolherParentesIntent",
        "EscolherSonsIntent",
        "EscolherOrdemIntent",
    )

    def can_handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        intent = ask_utils.get_intent_name(handler_input)

        if intent in self._INTENTS_MENU:
            if intent == "EscolherOrdemIntent" and session.get("aguardando_novo_jogo_ordem"):
                return True
            return False

        if session.get("ordem_ativo", False) or session.get("aguardando_novo_jogo_ordem", False):
            return True

        return intent in ("ResponderOrdemIntent", "ResponderJogoIntent")

    def _texto_confirmacao(self, handler_input):
        texto = obter_texto_usuario(handler_input)
        if not texto:
            texto = extrair_texto_do_evento_raw(handler_input) or ""
        return texto.strip()

    def _usuario_confirmou_sim(self, handler_input):
        intent = ask_utils.get_intent_name(handler_input)
        if intent in ("AMAZON.YesIntent", "ConfirmarNivelIntent"):
            return True
        if ask_utils.is_intent_name("EscolherOrdemIntent")(handler_input):
            return True
        texto = self._texto_confirmacao(handler_input)
        if interpretar_escolha_jogo(texto) == "ordem":
            return True
        return interpretar_confirmacao(texto) == "sim"

    def _usuario_confirmou_nao(self, handler_input):
        intent = ask_utils.get_intent_name(handler_input)
        if intent in ("AMAZON.NoIntent", "RecusarIntent"):
            return True
        texto = self._texto_confirmacao(handler_input)
        if interpretar_confirmacao(texto) == "nao":
            return True
        t = normalizar_texto(texto)
        return t in ("nao", "n", "no")

    def handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        session["ordem_ativo"] = True
        session["modo_jogo"] = "ordem"

        if session.get("aguardando_novo_jogo_ordem"):
            if self._usuario_confirmou_sim(handler_input):
                speak_output = iniciar_turno_ordem(session, "Ótimo! ")
                return (
                    handler_input.response_builder
                    .speak(speak_output)
                    .ask("Qual é a ordem correta?")
                    .response
                )
            if self._usuario_confirmou_nao(handler_input):
                session["ordem_ativo"] = False
                session["aguardando_novo_jogo_ordem"] = False
                session["ordem_atual"] = None
                session["aguardando_escolha_jogo"] = True
                return (
                    handler_input.response_builder
                    .speak(
                        "Tudo bem! Quer jogar memorizar palavras, jogo de parentes, "
                        "jogo de sons ou diga sair para encerrar."
                    )
                    .ask("O que você quer fazer?")
                    .response
                )
            return (
                handler_input.response_builder
                .speak("Não entendi. Diga sim para jogar de novo ou não para sair.")
                .ask("Sim ou não?")
                .response
            )

        if session.get("ordem_atual"):
            resposta = self._texto_confirmacao(handler_input)
            ordem_atual = session["ordem_atual"]
            passos = ordem_atual["passos"]
            pediu_ajuda = (
                ask_utils.is_intent_name("NaoEntendiOrdemIntent")(handler_input)
                or interpretar_pedido_ajuda_ordem(resposta)
            )

            if not resposta and not pediu_ajuda:
                return (
                    handler_input.response_builder
                    .speak(
                        "Não consegui entender. "
                        f"{ordem_atual['pergunta']}"
                    )
                    .ask("Qual é a ordem correta?")
                    .response
                )

            acertou = (
                False
                if pediu_ajuda
                else verificar_resposta_ordem(passos, resposta)
            )
            ordem_txt = formatar_ordem_correta(passos)

            if "ordens_perguntadas" not in session:
                session["ordens_perguntadas"] = []
            if ordem_atual["id"] not in session["ordens_perguntadas"]:
                session["ordens_perguntadas"].append(ordem_atual["id"])

            session["ordem_atual"] = None
            session["aguardando_novo_jogo_ordem"] = True

            if acertou:
                # Registrar acerto nas estatísticas da sessão
                session["session_acertos"] = session.get("session_acertos", 0) + 1
                feedback = f"Muito bem, você acertou! A ordem correta é: {ordem_txt}."
            elif pediu_ajuda:
                # Não conta como erro quando pediu ajuda
                feedback = f"Sem problema! A ordem correta é: {ordem_txt}."
            else:
                # Registrar erro nas estatísticas da sessão
                session["session_erros"] = session.get("session_erros", 0) + 1
                feedback = f"Quase! A ordem correta é: {ordem_txt}."

            speak_output = (
                f"{feedback} Quer jogar de novo ou sair? "
                f"Diga sim para jogar ou não para sair."
            )
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask("Sim para jogar de novo, ou não para sair.")
                .response
            )

        return (
            handler_input.response_builder
            .speak("Desculpe, ocorreu um erro no jogo de ordem.")
            .ask("Quer tentar de novo?")
            .response
        )


class JogoMemoriaPrincipalHandler(AbstractRequestHandler):
    """Jogo de memorizar palavras."""

    def can_handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        if session.get("parentes_ativo") or session.get("modo_jogo") == "parentes":
            return False
        if session.get("sons_ativo") or session.get("modo_jogo") == "sons":
            return False
        if session.get("ordem_ativo") or session.get("modo_jogo") == "ordem":
            return False
        return (
            session.get("jogo_ativo", False)
            or session.get("aguardando_confirmacao_nivel", False)
            or session.get("aguardando_novo_jogo", False)
            or ask_utils.is_intent_name("EscolherMemoriaIntent")(handler_input)
        )

    def handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes

        def usuario_confirmou_sim(handler_input):
            if ask_utils.is_intent_name("AMAZON.YesIntent")(handler_input):
                return True
            if ask_utils.is_intent_name("ConfirmarNivelIntent")(handler_input):
                return True
            return interpretar_confirmacao(obter_texto_usuario(handler_input)) == "sim"

        def usuario_confirmou_nao(handler_input):
            if ask_utils.is_intent_name("AMAZON.NoIntent")(handler_input):
                return True
            if ask_utils.is_intent_name("RecusarIntent")(handler_input):
                return True
            texto = obter_texto_usuario(handler_input) or extrair_texto_do_evento_raw(handler_input) or ""
            if interpretar_confirmacao(texto) == "nao":
                return True
            t = normalizar_texto(texto)
            return t in ("nao", "n", "no")

        if ask_utils.is_intent_name("EscolherMemoriaIntent")(handler_input):
            speak_output = iniciar_jogo_memoria(session)
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask("Repita as palavras que eu disse.")
                .response
            )

        if session.get("aguardando_confirmacao_nivel", False):
            if usuario_confirmou_sim(handler_input):
                nivel_atual = session["nivel"]
                if nivel_atual == "facil":
                    novo_nivel, qtd = "medio", 5
                elif nivel_atual == "medio":
                    novo_nivel, qtd = "dificil", 7
                else:
                    novo_nivel, qtd = "facil", 3
                palavras = gerar_palavras_aleatorias(qtd)
                session["jogo_ativo"] = True
                session["nivel"] = novo_nivel
                session["palavras"] = palavras
                session["rodada"] = 1
                session["aguardando_confirmacao_nivel"] = False
                sincronizar_dados_nuvem(handler_input, session)
                memoria = session.setdefault("memoria_salva", {})
                memoria["nivel_maximo"] = novo_nivel
                salvar_na_nuvem(session)
                speak_output = (
                    f"Ótimo! Nível {novo_nivel}! Palavras: {', '.join(palavras)}. Agora repita!"
                )
                return (
                    handler_input.response_builder
                    .speak(speak_output)
                    .ask("Repita as palavras.")
                    .response
                )
            if usuario_confirmou_nao(handler_input):
                session["aguardando_confirmacao_nivel"] = False
                session["jogo_ativo"] = False
                session["aguardando_escolha_jogo"] = True
                return (
                    handler_input.response_builder
                    .speak("Tudo bem! Quer jogar outra coisa? Memorizar palavras ou parentes?")
                    .ask("O que você quer jogar?")
                    .response
                )
            return (
                handler_input.response_builder
                .speak("Não entendi. Diga sim para continuar ou não para parar.")
                .ask("Sim ou não?")
                .response
            )

        if session.get("aguardando_novo_jogo", False):
            if usuario_confirmou_sim(handler_input):
                session["aguardando_novo_jogo"] = False
                speak_output = iniciar_jogo_memoria(session)
                return (
                    handler_input.response_builder
                    .speak(speak_output)
                    .ask("Repita as palavras.")
                    .response
                )
            if usuario_confirmou_nao(handler_input):
                session["aguardando_novo_jogo"] = False
                session["jogo_ativo"] = False
                session["aguardando_escolha_jogo"] = True
                return (
                    handler_input.response_builder
                    .speak("Tudo bem! Quer jogar memorizar palavras ou parentes?")
                    .ask("O que você quer jogar?")
                    .response
                )
            return (
                handler_input.response_builder
                .speak("Diga sim para jogar de novo ou não para escolher outro jogo.")
                .ask("Sim ou não?")
                .response
            )

        if session.get("jogo_ativo", False):
            palavras_esperadas = session["palavras"]
            resposta_usuario = obter_texto_usuario(handler_input)
            acertou = verificar_resposta(palavras_esperadas, resposta_usuario)

            if acertou:
                # Registrar acerto nas estatísticas da sessão
                session["session_acertos"] = session.get("session_acertos", 0) + 1
                rodada = session["rodada"]
                nivel = session["nivel"]

                if nivel == "facil" and rodada < 2:
                    session["rodada"] = rodada + 1
                    palavras_novas = gerar_palavras_aleatorias(3)
                    session["palavras"] = palavras_novas
                    speak_output = (
                        f"Parabéns! Mais 3 palavras: {', '.join(palavras_novas)}. "
                        f"Acerte de novo para ir ao nível médio. Agora repita!"
                    )
                    return (
                        handler_input.response_builder
                        .speak(speak_output)
                        .ask("Repita as palavras.")
                        .response
                    )
                if nivel == "facil" and rodada == 2:
                    session["aguardando_confirmacao_nivel"] = True
                    session["jogo_ativo"] = False
                    return (
                        handler_input.response_builder
                        .speak("Parabéns no nível fácil! Quer ir para o nível médio com 5 palavras?")
                        .ask("Diga sim ou não.")
                        .response
                    )
                if nivel == "medio" and rodada < 2:
                    session["rodada"] = rodada + 1
                    palavras_novas = gerar_palavras_aleatorias(5)
                    session["palavras"] = palavras_novas
                    speak_output = (
                        f"Parabéns! Mais 5 palavras: {', '.join(palavras_novas)}. Agora repita!"
                    )
                    return (
                        handler_input.response_builder
                        .speak(speak_output)
                        .ask("Repita as palavras.")
                        .response
                    )
                if nivel == "medio" and rodada == 2:
                    session["aguardando_confirmacao_nivel"] = True
                    session["jogo_ativo"] = False
                    return (
                        handler_input.response_builder
                        .speak("Parabéns no médio! Quer o nível difícil com 7 palavras?")
                        .ask("Diga sim ou não.")
                        .response
                    )
                if nivel == "dificil" and rodada < 2:
                    session["rodada"] = rodada + 1
                    palavras_novas = gerar_palavras_aleatorias(7)
                    session["palavras"] = palavras_novas
                    speak_output = f"Parabéns! Mais 7 palavras: {', '.join(palavras_novas)}. Repita!"
                    return (
                        handler_input.response_builder
                        .speak(speak_output)
                        .ask("Repita as palavras.")
                        .response
                    )

                session["jogo_ativo"] = False
                session["aguardando_novo_jogo"] = True
                sincronizar_dados_nuvem(handler_input, session)
                memoria = session.setdefault("memoria_salva", {})
                memoria["nivel_maximo"] = "dificil"
                memoria["completo"] = True
                salvar_na_nuvem(session)
                return (
                    handler_input.response_builder
                    .speak("Parabéns, você completou todos os níveis! Quer jogar de novo?")
                    .ask("Diga sim ou não.")
                    .response
                )

            # Registrar erro nas estatísticas da sessão
            session["session_erros"] = session.get("session_erros", 0) + 1
            
            session["jogo_ativo"] = False
            session["aguardando_novo_jogo"] = True
            return (
                handler_input.response_builder
                .speak(
                    f"Que pena! As palavras eram: {', '.join(palavras_esperadas)}. "
                    "Quer tentar de novo?"
                )
                .ask("Diga sim ou não.")
                .response
            )

        return (
            handler_input.response_builder
            .speak("Desculpe, não entendi. Pode repetir?")
            .ask("Pode repetir?")
            .response
        )


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        if not ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input):
            return False
        session = handler_input.attributes_manager.session_attributes
        return not session.get("sons_ativo", False) and not session.get("ordem_ativo", False)

    def handle(self, handler_input):
        speak_output = (
            "Posso ajudar com quatro jogos: memorizar palavras, com níveis fácil, médio e difícil; "
            "jogo de parentes, onde você cadastra familiares e responde perguntas; "
            "jogo de sons, onde você identifica sons do dia a dia; "
            "e jogo de ordem, onde você diz a sequência correta de passos no mercado, "
            "no hospital, no banco e em outras situações do dia a dia. "
            "Diga quero jogar para começar."
        )
        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask(speak_output)
            .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (
            ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input)
            or ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input)
        )

    def handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        session.clear()
        return (
            handler_input.response_builder
            .speak("Tchau! Até a próxima!")
            .response
        )


class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        import time
        session = handler_input.attributes_manager.session_attributes
        user_id = obter_user_id(handler_input)
        
        # Calcular tempo de uso da sessão
        if session.get("session_start_time") and user_id:
            tempo_minutos = (time.time() - session["session_start_time"]) / 60
            acertos = session.get("session_acertos", 0)
            erros = session.get("session_erros", 0)
            
            # Registrar estatísticas na API do Render
            if tempo_minutos > 0 or acertos > 0 or erros > 0:
                registrar_estatistica(user_id, tempo_minutos, acertos, erros)
                logger.info(f"Estatísticas registradas: tempo={tempo_minutos:.2f}min, acertos={acertos}, erros={erros}")
        
        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        intent_name = ask_utils.get_intent_name(handler_input)
        return (
            handler_input.response_builder
            .speak(f"Você acionou a intent {intent_name}.")
            .response
        )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.error(exception, exc_info=True)
        return (
            handler_input.response_builder
            .speak("Desculpe, tive um problema. Por favor, tente novamente.")
            .ask("Pode repetir?")
            .response
        )


class ShowStatsHandler(AbstractRequestHandler):
    """Handler para mostrar estatísticas quando usuário clica no botão de gráfico."""
    
    def can_handle(self, handler_input):
        return (
            ask_utils.is_request_type("Alexa.Presentation.APL.UserEvent")(handler_input)
            and handler_input.request_envelope.request.arguments
            and handler_input.request_envelope.request.arguments[0] == "show_stats"
        )
    
    def handle(self, handler_input):
        user_id = obter_user_id(handler_input)
        
        if not user_id or not render_disponivel():
            speak_output = "Não foi possível carregar suas estatísticas. O serviço não está disponível."
            return handler_input.response_builder.speak(speak_output).response
        
        try:
            # Carregar estatísticas da API
            from utils import carregar_dados_usuario
            dados = carregar_dados_usuario(user_id)
            memoria = dados.get("memoria", {})
            
            tempo_total = memoria.get("tempo_total", 0)
            daily_stats = memoria.get("estatisticas_diarias", [])
            
            # Só mostrar estatísticas se houver dados reais
            if tempo_total == 0 and not daily_stats:
                speak_output = "Você ainda não tem estatísticas registradas. Use a skill para começar a acumular dados."
                return handler_input.response_builder.speak(speak_output).response
            
            dados_estatisticas = {
                "totalTime": tempo_total,
                "dailyStats": daily_stats
            }
            
            # Mostrar tela de estatísticas no Echo Show
            if tem_suporte_apl(handler_input):
                mostrar_tela_estatisticas(handler_input, dados_estatisticas)
            
            speak_output = "Aqui estão suas estatísticas de uso."
            return handler_input.response_builder.speak(speak_output).response
            
        except Exception as e:
            logger.error(f"Erro ao carregar estatísticas: {e}")
            speak_output = "Desculpe, ocorreu um erro ao carregar suas estatísticas. Tente novamente mais tarde."
            return handler_input.response_builder.speak(speak_output).response


class GoBackHandler(AbstractRequestHandler):
    """Handler para voltar à tela principal quando usuário clica no botão de voltar."""
    
    def can_handle(self, handler_input):
        return (
            ask_utils.is_request_type("Alexa.Presentation.APL.UserEvent")(handler_input)
            and handler_input.request_envelope.request.arguments
            and handler_input.request_envelope.request.arguments[0] == "go_back"
        )
    
    def handle(self, handler_input):
        # Mostrar tela principal novamente
        if tem_suporte_apl(handler_input):
            mostrar_tela_principal(handler_input)
        
        speak_output = "Voltando para a tela principal."
        return handler_input.response_builder.speak(speak_output).response


class ConfiguracoesHandler(AbstractRequestHandler):
    """Handler para acessar configurações e ver estatísticas."""
    
    def can_handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        intent_name = ask_utils.get_intent_name(handler_input)
        logger.info(f"ConfiguracoesHandler - intent: {intent_name}, aguardando_escolha_jogo: {session.get('aguardando_escolha_jogo')}, aguardando_opcao_configuracoes: {session.get('aguardando_opcao_configuracoes')}")
        
        # Se estiver aguardando opção de configurações, não responder (deixa ExportarRelatorioHandler cuidar)
        if session.get("aguardando_opcao_configuracoes"):
            logger.info(f"ConfiguracoesHandler - aguardando_opcao_configuracoes, retornando False")
            return False
        
        # Responder a intent específica de configurações
        if ask_utils.is_intent_name("ConfiguracoesIntent")(handler_input):
            return True
        
        # Se estiver no menu de escolha de jogo e não for um intent de jogo específico,
        # pode ser uma solicitação de configurações
        if session.get("aguardando_escolha_jogo", False):
            intents_jogo = [
                "QueroJogarIntent",
                "EscolherMemoriaIntent", 
                "EscolherParentesIntent",
                "EscolherSonsIntent",
                "EscolherOrdemIntent",
                "AMAZON.YesIntent",
                "AMAZON.NoIntent",
                "AMAZON.CancelIntent",
                "AMAZON.StopIntent"
            ]
            if intent_name not in intents_jogo:
                logger.info(f"ConfiguracoesHandler - intent não é de jogo, pode ser configurações")
                return True
        
        return False
    
    def handle(self, handler_input):
        import time
        user_id = obter_user_id(handler_input)
        session = handler_input.attributes_manager.session_attributes
        session["aguardando_opcao_configuracoes"] = False
        
        # Calcular tempo da sessão atual
        tempo_atual = 0
        if session.get("session_start_time"):
            tempo_atual = (time.time() - session["session_start_time"]) / 60  # converter para minutos
        
        acertos_sessao = session.get("session_acertos", 0)
        erros_sessao = session.get("session_erros", 0)
        
        if tempo_atual < 1:
            tempo_str = f"{int(tempo_atual * 60)} segundos"
        else:
            tempo_str = f"{int(tempo_atual)} minutos"
        
        speak_output = (
            f"Nas configurações você pode ver suas estatísticas. "
            f"Nesta sessão você usou a skill por {tempo_str}, "
            f"com {acertos_sessao} acertos e {erros_sessao} erros. "
        )
        
        # Tentar carregar estatísticas históricas
        if user_id and render_disponivel():
            try:
                from utils import carregar_dados_usuario
                dados = carregar_dados_usuario(user_id)
                memoria = dados.get("memoria", {})
                
                tempo_total = memoria.get("tempo_total", 0)
                daily_stats = memoria.get("estatisticas_diarias", [])
                
                if tempo_total > 0:
                    speak_output += f"Seu tempo total de uso é de {int(tempo_total)} minutos. "
                
                if daily_stats:
                    hoje_stats = daily_stats[-1] if daily_stats else None
                    if hoje_stats:
                        speak_output += (
                            f"Hoje você teve {hoje_stats.get('correct', 0)} acertos "
                            f"e {hoje_stats.get('wrong', 0)} erros. "
                        )
            except Exception as e:
                logger.error(f"Erro ao carregar estatísticas: {e}")
        
        speak_output += "Você também pode pedir para exportar um relatório em PDF. O que mais quer fazer?"
        
        # Definir flag para aguardar solicitação de exportação
        session["aguardando_opcao_configuracoes"] = True
        
        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask("Quer jogar algum jogo ou exportar um relatório?")
            .response
        )


class ExportarRelatorioHandler(AbstractRequestHandler):
    """Handler para exportar relatório PDF quando usuário solicita."""
    
    def can_handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        intent_name = ask_utils.get_intent_name(handler_input)
        
        # Responder a intent específica de exportar relatório
        if ask_utils.is_intent_name("ExportarRelatorioIntent")(handler_input):
            return True
        
        # Se estiver aguardando confirmação de PDF
        if session.get("aguardando_confirmacao_pdf") and ask_utils.is_intent_name("AMAZON.YesIntent")(handler_input):
            return True
        
        # Se estiver aguardando opção de configurações e não for um intent de jogo
        if session.get("aguardando_opcao_configuracoes"):
            intents_jogo = [
                "QueroJogarIntent",
                "EscolherMemoriaIntent", 
                "EscolherParentesIntent",
                "EscolherSonsIntent",
                "EscolherOrdemIntent",
                "ConfiguracoesIntent",
                "AMAZON.CancelIntent",
                "AMAZON.StopIntent",
                "AMAZON.HelpIntent"
            ]
            if intent_name not in intents_jogo:
                logger.info(f"ExportarRelatorioHandler - aguardando_opcao_configuracoes, intent não é de jogo: {intent_name}")
                return True
        
        # Detectar palavras-chave no texto
        texto = obter_texto_usuario(handler_input).lower()
        logger.info(f"ExportarRelatorioHandler - intent: {intent_name}, texto: '{texto}'")
        
        if texto and any(palavra in texto for palavra in ["exportar", "pdf", "relatório", "relatorio", "baixar"]):
            logger.info(f"ExportarRelatorioHandler - detectou palavra de exportação")
            return True
        
        return False
    
    def handle(self, handler_input):
        user_id = obter_user_id(handler_input)
        session = handler_input.attributes_manager.session_attributes
        session["aguardando_confirmacao_pdf"] = False
        session["aguardando_opcao_configuracoes"] = False
        
        logger.info(f"ExportarRelatorioHandler - user_id: {user_id}, render_disponivel: {render_disponivel()}")
        
        if not user_id:
            logger.error(f"ExportarRelatorioHandler - Falha: user_id={user_id}")
            speak_output = "Não foi possível gerar o relatório. Tente novamente mais tarde."
            return handler_input.response_builder.speak(speak_output).response
        
        link_pdf = obter_link_pdf(user_id)
        
        if not link_pdf:
            speak_output = "Não foi possível gerar o link do relatório."
            return handler_input.response_builder.speak(speak_output).response
        
        speak_output = (
            "Seu relatório em PDF está pronto! "
            "Enviei o link para o card no aplicativo Alexa do seu celular. "
            "Abra o link no navegador e o download começará automaticamente."
        )
        
        return (
            handler_input.response_builder
            .speak(speak_output)
            .set_card(
                SimpleCard(
                    title="Relatório Dona Memória (PDF)",
                    content=f"Toque no link abaixo ou copie no navegador para baixar:\n\n{link_pdf}",
                )
            )
            .ask("Quer fazer mais alguma coisa?")
            .response
        )


class JogoNaoPertenceHandler(AbstractRequestHandler):
    """Handler para o jogo 'Qual não pertence'."""
    
    def can_handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        return (
            ask_utils.is_intent_name("EscolherNaoPertenceIntent")(handler_input)
            or session.get("jogo_nao_pertence_ativo", False)
        )
    
    def handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        
        # Se o jogo já está ativo, processa a resposta do usuário
        if session.get("jogo_nao_pertence_ativo", False):
            return self._processar_resposta(handler_input, session)
        
        # Inicia um novo jogo
        return self._iniciar_jogo(handler_input, session)
    
    def _iniciar_jogo(self, handler_input, session):
        """Inicia uma nova rodada do jogo."""
        dados_jogo = obter_aleatorio_jogo_nao_pertence()
        
        session["jogo_nao_pertence_ativo"] = True
        session["resposta_correta_nao_pertence"] = dados_jogo["resposta_correta"]
        session["tema_atual"] = dados_jogo["tema"]
        
        # Falar os nomes dos itens para Echo Dot
        nomes_itens = [item["nome"] for item in dados_jogo["itens"]]
        texto_falado = (
            f"Vamos jogar 'Qual não pertence'! O tema é {dados_jogo['tema']}. "
            f"Olhe para as imagens e me diga qual destes itens não pertence ao tema: "
            f"{', '.join(nomes_itens)}. "
            "Qual você escolhe?"
        )
        
        response_builder = handler_input.response_builder.speak(texto_falado).ask("Qual imagem não pertence ao tema?")
        
        # Mostrar imagens no Echo Show
        if tem_suporte_apl(handler_input):
            mostrar_tela_jogo_nao_pertence(handler_input, dados_jogo["tema"], dados_jogo["itens"])
        
        return response_builder.response
    
    def _processar_resposta(self, handler_input, session):
        """Processa a resposta do usuário."""
        texto_usuario = obter_texto_usuario(handler_input) or ""
        resposta_usuario = normalizar_texto(texto_usuario)
        resposta_correta = session.get("resposta_correta_nao_pertence", "")
        
        # Verificar se a resposta está correta
        if resposta_usuario in resposta_correta or resposta_correta in resposta_usuario:
            speak_output = "Muito bem! Você acertou! "
            session["acertos_nao_pertence"] = session.get("acertos_nao_pertence", 0) + 1
        else:
            speak_output = f"Não foi dessa vez. A resposta correta era {resposta_correta}. "
            session["erros_nao_pertence"] = session.get("erros_nao_pertence", 0) + 1
        
        # Pergunta se quer jogar de novo
        session["jogo_nao_pertence_ativo"] = False
        speak_output += "Quer jogar de novo?"
        
        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask("Diga sim para jogar de novo, ou não para sair.")
            .response
        )


sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(ConfiguracoesHandler())
sb.add_request_handler(ExportarRelatorioHandler())
sb.add_request_handler(MenuJogoHandler())
sb.add_request_handler(JogoSonsHandler())
sb.add_request_handler(JogoOrdemHandler())
sb.add_request_handler(JogoParentesHandler())
sb.add_request_handler(JogoMemoriaPrincipalHandler())
sb.add_request_handler(JogoNaoPertenceHandler())
sb.add_request_handler(ShowStatsHandler())
sb.add_request_handler(GoBackHandler())
sb.add_request_handler(IntentReflectorHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()