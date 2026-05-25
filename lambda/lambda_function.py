# -*- coding: utf-8 -*-

import logging
import ask_sdk_core.utils as ask_utils

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model import Response

from utils import (
    adicionar_parente,
    carregar_dados_usuario,
    formatar_parentes_cadastrados,
    gerar_palavras_aleatorias,
    gerar_pergunta_parentes,
    interpretar_confirmacao,
    interpretar_escolha_jogo,
    interpretar_pronto_parentes,
    render_disponivel,
    salvar_dados_usuario,
    verificar_nome_parente,
    verificar_resposta,
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
    session["people"] = dados.get("people", {})
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
    resposta_slot = ask_utils.get_slot_value(handler_input=handler_input, slot_name="resposta") or ""
    if resposta_slot:
        return resposta_slot
    person_name = ask_utils.get_slot_value(handler_input=handler_input, slot_name="personName") or ""
    relation = ask_utils.get_slot_value(handler_input=handler_input, slot_name="relation") or ""
    if person_name and relation:
        return f"{person_name} {relation}"

    request = handler_input.request_envelope.request
    if hasattr(request, "intent") and request.intent and request.intent.slots:
        valores = [s.value for s in request.intent.slots.values() if s.value]
        if valores:
            return " ".join(valores)
    if hasattr(request, "input_transcript") and request.input_transcript:
        return request.input_transcript
    return ""


def iniciar_jogo_memoria(session_attrs):
    palavras = gerar_palavras_aleatorias(3)
    session_attrs["modo_jogo"] = "memoria"
    session_attrs["jogo_ativo"] = True
    session_attrs["parentes_ativo"] = False
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


def iniciar_modo_parentes(session_attrs, prefixo=""):
    session_attrs["modo_jogo"] = "parentes"
    session_attrs["parentes_ativo"] = True
    session_attrs["jogo_ativo"] = False
    session_attrs["aguardando_escolha_jogo"] = False
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
        session = handler_input.attributes_manager.session_attributes
        sincronizar_dados_nuvem(handler_input, session)
        session["aguardando_escolha_jogo"] = True
        session["jogo_ativo"] = False
        session["parentes_ativo"] = False

        extra = ""
        if session.get("people"):
            extra = "Bom te ver de novo! Seus parentes continuam cadastrados. "

        speak_output = (
            f"Olá, eu sou a Dona Memória! {extra}"
            "Você pode jogar memorizar palavras ou o jogo de parentes. O que você quer jogar?"
        )
        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask("Diga memorizar palavras ou jogo de parentes.")
            .response
        )


class MenuJogoHandler(AbstractRequestHandler):
    """Menu: escolher entre memorizar palavras ou jogo de parentes."""

    def can_handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        return (
            ask_utils.is_intent_name("QueroJogarIntent")(handler_input)
            or ask_utils.is_intent_name("EscolherMemoriaIntent")(handler_input)
            or ask_utils.is_intent_name("EscolherParentesIntent")(handler_input)
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

        session["aguardando_escolha_jogo"] = True
        speak_output = (
            "Temos dois jogos: memorizar palavras ou parentes. "
            "Qual você quer? Diga memorizar palavras ou jogo de parentes."
        )
        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask("Memorizar palavras ou jogo de parentes?")
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

        # Cadastrar parente
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
            if not session["people"]:
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

        # Responder pergunta
        if session.get("parentes_fase") == "pergunta" and session.get("pergunta_atual"):
            resposta = obter_texto_usuario(handler_input)
            pergunta = session["pergunta_atual"]
            nomes = pergunta["nomes_esperados"]
            acertou = verificar_nome_parente(nomes, resposta)

            if acertou:
                proxima = gerar_pergunta_parentes(session["people"])
                session["pergunta_atual"] = proxima
                speak_output = (
                    f"Muito bem, você acertou! Próxima pergunta: {proxima['pergunta']}"
                )
            else:
                nomes_txt = " e ".join(nomes)
                proxima = gerar_pergunta_parentes(session["people"])
                session["pergunta_atual"] = proxima
                speak_output = (
                    f"Quase! O correto era {nomes_txt}. "
                    f"Vamos para outra: {proxima['pergunta']}"
                )
            return (
                handler_input.response_builder
                .speak(speak_output)
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


class JogoMemoriaPrincipalHandler(AbstractRequestHandler):
    """Jogo de memorizar palavras."""

    def can_handle(self, handler_input):
        session = handler_input.attributes_manager.session_attributes
        if session.get("parentes_ativo") or session.get("modo_jogo") == "parentes":
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
            return interpretar_confirmacao(obter_texto_usuario(handler_input)) == "nao"

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
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        speak_output = (
            "Posso ajudar com dois jogos: memorizar palavras, com níveis fácil, médio e difícil; "
            "ou jogo de parentes, onde você cadastra familiares e responde perguntas. "
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


sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(MenuJogoHandler())
sb.add_request_handler(JogoParentesHandler())
sb.add_request_handler(JogoMemoriaPrincipalHandler())
sb.add_request_handler(IntentReflectorHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
