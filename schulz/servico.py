"""Orquestração do processamento: ingestão → cálculo → emissão → persistência, com idempotência.

Equivale, numa única chamada, ao pipeline da nuvem (``fn-ingestao`` → ``fn-certificado``):

1. calcula o SHA-256 e o tamanho do arquivo recebido (só isso vai para o log);
2. se o mesmo hash já foi registrado, encerra como ``DUPLICADA`` sem abrir o Excel (RN-20);
3. valida e lê a planilha; fora do contrato → ``REJEITADA`` com os erros (linha, coluna, regra);
4. calcula média, erro, status e parecer; gera o PDF com QR Code e grava → ``EMITIDA``.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import string
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import calculo, certificado, ingestao
from .repositorio import DUPLICADA, EMITIDA, REJEITADA, HashJaRegistrado, Registro, Repositorio, agora_utc

log = logging.getLogger("schulz")

ALFABETO_TOKEN = string.ascii_letters + string.digits
TAMANHO_TOKEN = 32


@dataclass
class Configuracao:
    pasta_dados: Path
    url_base: str  # base da URL pública do QR Code, sem barra final
    gerado_por: str  # nome de exibição: só no PDF, nunca na tabela nem no log


class Servico:
    def __init__(self, config: Configuracao):
        self.config = config
        self.repositorio = Repositorio(config.pasta_dados / "calibracoes.db")
        self.pasta_pdf = config.pasta_dados / "certificados"
        self.pasta_pdf.mkdir(parents=True, exist_ok=True)

    def processar(self, conteudo: bytes) -> Registro:
        inicio = time.perf_counter()
        sha256 = hashlib.sha256(conteudo).hexdigest()
        tamanho = len(conteudo)
        id = str(uuid.uuid4())
        agora = agora_utc()

        original = self.repositorio.buscar_original_por_hash(sha256)
        if original is not None:
            return self._duplicada(id, agora, sha256, tamanho, original, inicio)

        try:
            pontos = ingestao.ler(conteudo)
        except ingestao.PlanilhaInvalida as e:
            erros = [x.como_dict() for x in e.erros]
            try:
                self.repositorio.inserir(id=id, criado_em=agora, sha256_planilha=sha256, bytes_=tamanho,
                                         estado=REJEITADA, erros=erros, duracao_ms=_ms(inicio))
            except HashJaRegistrado:
                return self._duplicada(id, agora, sha256, tamanho,
                                       self.repositorio.buscar_original_por_hash(sha256), inicio)
            self._log(id, sha256, tamanho, REJEITADA, None, inicio, regras=",".join(sorted({x.regra for x in e.erros})))
            return self.repositorio.buscar(id)

        resultado = calculo.calcular(pontos)
        token = "".join(secrets.choice(ALFABETO_TOKEN) for _ in range(TAMANHO_TOKEN))
        url = f"{self.config.url_base}/verificar/{token}"
        pdf = certificado.gerar(certificado.DadosCertificado(
            id=id, emitido_em=agora, sha256_planilha=sha256, gerado_por=self.config.gerado_por,
            resultado=resultado, token=token, url_verificacao=url))
        sha256_pdf = hashlib.sha256(pdf).hexdigest()
        caminho = self.caminho_pdf(id)
        caminho.write_bytes(pdf)
        try:
            self.repositorio.inserir(id=id, criado_em=agora, sha256_planilha=sha256, bytes_=tamanho, estado=EMITIDA,
                                     parecer=resultado.parecer, resultado=resultado_para_dict(resultado),
                                     token=token, sha256_pdf=sha256_pdf, duracao_ms=_ms(inicio))
        except HashJaRegistrado:
            # Outra requisição com o mesmo arquivo terminou antes: este PDF não vale.
            caminho.unlink(missing_ok=True)
            return self._duplicada(id, agora, sha256, tamanho,
                                   self.repositorio.buscar_original_por_hash(sha256), inicio)
        self._log(id, sha256, tamanho, EMITIDA, resultado.parecer, inicio)
        return self.repositorio.buscar(id)

    def caminho_pdf(self, id: str) -> Path:
        # O id vem de uuid4 ou já foi validado na rota; o nome do arquivo nunca vem do usuário.
        return self.pasta_pdf / f"{uuid.UUID(id)}.pdf"

    def _duplicada(self, id, agora, sha256, tamanho, original: Registro, inicio) -> Registro:
        self.repositorio.inserir(id=id, criado_em=agora, sha256_planilha=sha256, bytes_=tamanho, estado=DUPLICADA,
                                 id_original=original.id, duracao_ms=_ms(inicio))
        self._log(id, sha256, tamanho, DUPLICADA, None, inicio, original=original.id)
        return self.repositorio.buscar(id)

    @staticmethod
    def _log(id, sha256, tamanho, estado, parecer, inicio, **extra) -> None:
        # 🔒 Só id, hash, tamanho e resultado: nunca nome do arquivo, conteúdo, token ou usuário.
        complemento = "".join(f" {k}={v}" for k, v in extra.items())
        log.info("Processamento: id=%s sha256=%s bytes=%d resultado=%s parecer=%s ms=%d%s",
                 id, sha256, tamanho, estado, parecer or "-", _ms(inicio), complemento)


def _ms(inicio: float) -> int:
    return int(round((time.perf_counter() - inicio) * 1000))


def resultado_para_dict(resultado: calculo.ResultadoCalibracao) -> list[dict[str, Any]]:
    """Valores metrológicos como texto (escala preservada), como a API Java e o DynamoDB (D-023)."""
    return [{
        "caracteristica": r.ponto.caracteristica,
        "leituras": [calculo.texto_plano(l) for l in r.ponto.leituras],
        "valorReferencia": calculo.texto_plano(r.ponto.valor_referencia),
        "media": calculo.texto_plano(r.media),
        "erroSistematico": calculo.texto_plano(r.erro_sistematico),
        "lea": calculo.texto_plano(r.ponto.lea),
        "status": r.status,
        "exibicao": {
            "valorReferencia": calculo.exibir(r.ponto.valor_referencia),
            "media": calculo.exibir(r.media),
            "erroSistematico": calculo.exibir(r.erro_sistematico),
            "lea": calculo.exibir(r.ponto.lea),
        },
    } for r in resultado.pontos]
