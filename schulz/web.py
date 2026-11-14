"""API HTTP e interface local (Flask).

Rotas:

- ``GET  /``                                      interface (processar planilha, histórico, exemplos)
- ``GET  /verificar/<token>``                     página pública de verificação (aberta pelo QR Code)
- ``GET  /api/saude``                             usada pelo ``.bat`` para saber quando abrir o navegador
- ``POST /api/calibracoes/processamento``         multipart, campo ``arquivo`` (.xlsx até 5 MB)
- ``GET  /api/calibracoes``                       20 envios mais recentes + indicadores
- ``GET  /api/calibracoes/<id>``                  um envio
- ``GET  /api/calibracoes/<id>/certificado``      PDF do certificado
- ``GET  /api/verificacao/<token>``               dados públicos do certificado (sem nome, sem planilha)
- ``POST /api/verificacao/<token>/conferencia``   confere o SHA-256 de um PDF recebido
- ``GET  /api/exemplos`` e ``/api/exemplos/<nome>`` planilhas sintéticas do repositório

Erros em ``application/problem+json`` (RFC 9457); 500 devolve só um ``id`` que liga ao log.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request, send_file, send_from_directory
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from . import VERSAO, ingestao
from .repositorio import DUPLICADA, EMITIDA, REJEITADA, Registro
from .servico import Servico

log = logging.getLogger("schulz")

RAIZ = Path(__file__).resolve().parents[1]
PASTA_EXEMPLOS = RAIZ / "nucleo" / "src" / "test" / "resources" / "planilhas"
NOME_EXEMPLO = re.compile(r"(ok|inv)-[A-Za-z0-9-]+\.xlsx")
TOKEN = re.compile(r"[A-Za-z0-9]{32}")
PROBLEM_JSON = "application/problem+json"
FOLGA_MULTIPART = 64 * 1024


def criar_app(servico: Servico) -> Flask:
    app = Flask(__name__, static_folder="estatico", static_url_path="/estatico")
    # Acima disto o Werkzeug responde 413 sem ler o corpo; entre 5 MB e o teto, a R01 responde 400.
    app.config["MAX_CONTENT_LENGTH"] = ingestao.MAXIMO_BYTES + FOLGA_MULTIPART
    app.config["JSON_SORT_KEYS"] = False
    app.json.sort_keys = False
    app.json.ensure_ascii = False

    @app.after_request
    def cabecalhos_de_seguranca(resposta: Response) -> Response:
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["Referrer-Policy"] = "no-referrer"
        resposta.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if request.path.startswith("/api/"):
            resposta.headers["Cache-Control"] = "no-store"
        return resposta

    # --- páginas ------------------------------------------------------------------------------

    @app.get("/")
    def inicio():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/verificar/<token>")
    def pagina_verificacao(token: str):
        return send_from_directory(app.static_folder, "verificar.html")

    # --- API ----------------------------------------------------------------------------------

    @app.get("/api/saude")
    def saude():
        return jsonify(status="ok", versao=VERSAO)

    @app.post("/api/calibracoes/processamento")
    def processar():
        if not (request.mimetype or "").startswith("multipart/form-data"):
            return problema(415, "Tipo de mídia não suportado", "Envie a planilha como multipart/form-data.")
        arquivo = request.files.get("arquivo")
        if arquivo is None:
            return problema(400, "Requisição inválida", "Falta a parte 'arquivo' com a planilha.")
        # O corpo inteiro já é limitado pelo MAX_CONTENT_LENGTH (5 MB + folga do multipart); ler tudo
        # deixa o SHA-256 ser o do arquivo inteiro, também quando a R01 o rejeita.
        conteudo = arquivo.stream.read()
        registro = servico.processar(conteudo)
        corpo = registro_para_dict(registro, servico)
        if registro.estado == REJEITADA:
            return problema(400, "Planilha fora do contrato",
                            f"{len(registro.erros)} erro(s) encontrado(s). Corrija e envie de novo.",
                            erros=registro.erros, id=registro.id, estado=REJEITADA)
        return jsonify(corpo)

    @app.get("/api/calibracoes")
    def historico():
        return jsonify(indicadores=servico.repositorio.indicadores(),
                       calibracoes=[registro_para_dict(r, servico, resumo=True)
                                    for r in servico.repositorio.recentes(20)])

    @app.get("/api/calibracoes/<id>")
    def uma_calibracao(id: str):
        registro = _buscar(id)
        if registro is None:
            return problema(404, "Não encontrado", "Calibração não encontrada.")
        return jsonify(registro_para_dict(registro, servico))

    @app.get("/api/calibracoes/<id>/certificado")
    def baixar_certificado(id: str):
        registro = _buscar(id)
        if registro is None or registro.estado != EMITIDA:
            return problema(404, "Não encontrado", "Certificado não encontrado.")
        caminho = servico.caminho_pdf(registro.id)
        if not caminho.is_file():
            return problema(404, "Não encontrado", "Arquivo do certificado não encontrado.")
        return send_file(caminho, mimetype="application/pdf", as_attachment=True,
                         download_name=f"certificado-{registro.id}.pdf", max_age=0)

    @app.get("/api/verificacao/<token>")
    def verificar(token: str):
        registro = _por_token(token)
        if registro is None:
            return problema(404, "Não encontrado", "Certificado não encontrado.")
        # Rota pública: sem nome de usuário, sem hash da planilha, sem pontos.
        return jsonify(id=registro.id, emitidoEm=registro.criado_em, parecer=registro.parecer,
                       sha256Pdf=registro.sha256_pdf)

    @app.post("/api/verificacao/<token>/conferencia")
    def conferir(token: str):
        registro = _por_token(token)
        if registro is None:
            return problema(404, "Não encontrado", "Certificado não encontrado.")
        arquivo = request.files.get("arquivo")
        if arquivo is None:
            return problema(400, "Requisição inválida", "Falta a parte 'arquivo' com o PDF.")
        sha256 = hashlib.sha256(arquivo.stream.read(ingestao.MAXIMO_BYTES + 1)).hexdigest()
        return jsonify(confere=sha256 == registro.sha256_pdf, sha256Recebido=sha256, sha256Pdf=registro.sha256_pdf)

    @app.get("/api/exemplos")
    def exemplos():
        nomes = sorted(p.name for p in PASTA_EXEMPLOS.glob("*.xlsx") if NOME_EXEMPLO.fullmatch(p.name)) \
            if PASTA_EXEMPLOS.is_dir() else []
        return jsonify(exemplos=[{"nome": n, "valida": n.startswith("ok-"), "url": f"/api/exemplos/{n}"}
                                 for n in nomes])

    @app.get("/api/exemplos/<nome>")
    def baixar_exemplo(nome: str):
        if not NOME_EXEMPLO.fullmatch(nome):
            return problema(404, "Não encontrado", "Exemplo não encontrado.")
        return send_from_directory(PASTA_EXEMPLOS, nome, as_attachment=True, max_age=0)

    # --- erros --------------------------------------------------------------------------------

    @app.errorhandler(RequestEntityTooLarge)
    def grande_demais(_):
        return problema(413, "Arquivo grande demais", "O arquivo excede o limite de 5 MB.")

    @app.errorhandler(HTTPException)
    def erro_http(e: HTTPException):
        if request.path.startswith("/api/"):
            return problema(e.code or 500, e.name, e.description or e.name)
        return e

    @app.errorhandler(Exception)
    def erro_inesperado(e: Exception):
        id_erro = str(uuid.uuid4())
        log.exception("Erro inesperado: id=%s rota=%s", id_erro, request.path)
        return problema(500, "Erro interno", "Erro inesperado. Informe o id ao suporte.", id=id_erro)

    def _buscar(id: str) -> Registro | None:
        try:
            uuid.UUID(id)
        except ValueError:
            return None
        return servico.repositorio.buscar(id)

    def _por_token(token: str) -> Registro | None:
        return servico.repositorio.buscar_por_token(token) if TOKEN.fullmatch(token) else None

    return app


def problema(status: int, titulo: str, detalhe: str, **extra: Any) -> Response:
    corpo = {"type": "about:blank", "title": titulo, "status": status, "detail": detalhe, **extra}
    resposta = jsonify(corpo)
    resposta.status_code = status
    resposta.mimetype = PROBLEM_JSON
    return resposta


def registro_para_dict(r: Registro, servico: Servico, resumo: bool = False) -> dict[str, Any]:
    corpo: dict[str, Any] = {
        "id": r.id,
        "criadoEm": r.criado_em,
        "reterAte": r.reter_ate,
        "estado": r.estado,
        "parecer": r.parecer,
        "bytes": r.bytes,
        "sha256Planilha": r.sha256_planilha,
        "duracaoMs": r.duracao_ms,
    }
    if r.estado == EMITIDA:
        corpo["certificado"] = {
            "url": f"/api/calibracoes/{r.id}/certificado",
            "sha256Pdf": r.sha256_pdf,
            "urlVerificacao": f"{servico.config.url_base}/verificar/{r.token}",
        }
    if r.estado == REJEITADA:
        corpo["quantidadeErros"] = len(r.erros or [])
    if r.estado == DUPLICADA:
        corpo["idOriginal"] = r.id_original
        if not resumo:
            original = servico.repositorio.buscar(r.id_original)
            corpo["original"] = registro_para_dict(original, servico) if original else None
    if not resumo:
        corpo["pontos"] = r.resultado
        corpo["erros"] = r.erros
    return corpo
