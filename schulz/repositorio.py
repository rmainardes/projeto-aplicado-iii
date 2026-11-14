"""Persistência local em SQLite (biblioteca padrão) — equivalente local da tabela ``calibracoes`` (D-021).

Estados: ``REJEITADA`` (fora do contrato, com os erros), ``EMITIDA`` (calculada e com PDF) e
``DUPLICADA`` (mesmo SHA-256 de um envio anterior, com ponteiro ``id_original``; RN-20). Na nuvem
existem ainda ``PROCESSANDO`` e ``PROCESSADA``, porque lá o cálculo e a emissão são funções
separadas; aqui os dois passos rodam na mesma requisição.

Idempotência: índice único parcial em ``sha256_planilha`` para os registros originais. Duas
requisições simultâneas com o mesmo arquivo não geram dois certificados: a segunda perde a corrida
no ``INSERT`` e vira ``DUPLICADA``.

🔒 Não há coluna para nome de arquivo, conteúdo da planilha nem nome do usuário (LGPD): só id,
hashes, tamanho, estado, resultado calculado, token e datas.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

REJEITADA = "REJEITADA"
EMITIDA = "EMITIDA"
DUPLICADA = "DUPLICADA"
RETENCAO_ANOS = 5  # ISO/IEC 17025 (D-004)

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS calibracoes (
    id               TEXT PRIMARY KEY,
    criado_em        TEXT NOT NULL,
    reter_ate        TEXT NOT NULL,
    sha256_planilha  TEXT NOT NULL,
    bytes            INTEGER NOT NULL,
    estado           TEXT NOT NULL CHECK (estado IN ('REJEITADA', 'EMITIDA', 'DUPLICADA')),
    parecer          TEXT CHECK (parecer IN ('APROVADO', 'REPROVADO')),
    resultado_json   TEXT,
    erros_json       TEXT,
    token            TEXT UNIQUE,
    sha256_pdf       TEXT,
    id_original      TEXT REFERENCES calibracoes(id),
    duracao_ms       INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_calibracoes_hash_original
    ON calibracoes(sha256_planilha) WHERE id_original IS NULL;
CREATE INDEX IF NOT EXISTS ix_calibracoes_criado_em ON calibracoes(criado_em);
"""


class HashJaRegistrado(Exception):
    """Outro envio com o mesmo SHA-256 já foi registrado (corrida perdida no índice único)."""


@dataclass(frozen=True)
class Registro:
    id: str
    criado_em: str
    reter_ate: str
    sha256_planilha: str
    bytes: int
    estado: str
    parecer: str | None
    resultado: list[dict[str, Any]] | None
    erros: list[dict[str, Any]] | None
    token: str | None
    sha256_pdf: str | None
    id_original: str | None
    duracao_ms: int | None


def agora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _reter_ate(instante: datetime) -> str:
    try:
        return instante.replace(year=instante.year + RETENCAO_ANOS).isoformat()
    except ValueError:  # 29/02
        return instante.replace(year=instante.year + RETENCAO_ANOS, day=28).isoformat()


class Repositorio:
    def __init__(self, arquivo: Path):
        self.arquivo = arquivo
        self._trava = threading.Lock()
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        with self._conexao() as c:
            c.executescript(_ESQUEMA)

    @contextmanager
    def _conexao(self) -> Iterator[sqlite3.Connection]:
        conexao = sqlite3.connect(self.arquivo, timeout=10)
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA foreign_keys = ON")
        try:
            with conexao:  # commit no sucesso, rollback na exceção
                yield conexao
        finally:
            conexao.close()

    # --- escrita ------------------------------------------------------------------------------

    def inserir(self, *, id: str, criado_em: datetime, sha256_planilha: str, bytes_: int, estado: str,
                parecer: str | None = None, resultado: list | None = None, erros: list | None = None,
                token: str | None = None, sha256_pdf: str | None = None, id_original: str | None = None,
                duracao_ms: int | None = None) -> None:
        try:
            with self._trava, self._conexao() as c:
                c.execute(
                    """INSERT INTO calibracoes (id, criado_em, reter_ate, sha256_planilha, bytes, estado, parecer,
                           resultado_json, erros_json, token, sha256_pdf, id_original, duracao_ms)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (id, criado_em.isoformat(), _reter_ate(criado_em), sha256_planilha, bytes_, estado, parecer,
                     None if resultado is None else json.dumps(resultado, ensure_ascii=False),
                     None if erros is None else json.dumps(erros, ensure_ascii=False),
                     token, sha256_pdf, id_original, duracao_ms))
        except sqlite3.IntegrityError as e:
            if "sha256_planilha" in str(e) or "ux_calibracoes_hash_original" in str(e):
                raise HashJaRegistrado() from e
            raise

    # --- leitura ------------------------------------------------------------------------------

    def buscar(self, id: str) -> Registro | None:
        return self._um("SELECT * FROM calibracoes WHERE id = ?", (id,))

    def buscar_original_por_hash(self, sha256: str) -> Registro | None:
        return self._um("SELECT * FROM calibracoes WHERE sha256_planilha = ? AND id_original IS NULL", (sha256,))

    def buscar_por_token(self, token: str) -> Registro | None:
        return self._um("SELECT * FROM calibracoes WHERE token = ? AND estado = 'EMITIDA'", (token,))

    def recentes(self, limite: int = 20) -> list[Registro]:
        with self._conexao() as c:
            linhas = c.execute("SELECT * FROM calibracoes ORDER BY criado_em DESC, rowid DESC LIMIT ?",
                               (limite,)).fetchall()
        return [_registro(l) for l in linhas]

    def indicadores(self) -> dict[str, int]:
        with self._conexao() as c:
            l = c.execute(
                """SELECT COUNT(*) AS envios,
                          SUM(estado = 'EMITIDA') AS emitidos,
                          SUM(parecer = 'APROVADO' AND estado = 'EMITIDA') AS aprovados,
                          SUM(parecer = 'REPROVADO' AND estado = 'EMITIDA') AS reprovados,
                          SUM(estado = 'REJEITADA') AS rejeitadas,
                          SUM(estado = 'DUPLICADA') AS duplicadas
                   FROM calibracoes""").fetchone()
        return {k: int(l[k] or 0) for k in l.keys()}

    def _um(self, sql: str, parametros: tuple) -> Registro | None:
        with self._conexao() as c:
            linha = c.execute(sql, parametros).fetchone()
        return None if linha is None else _registro(linha)


def _registro(l: sqlite3.Row) -> Registro:
    return Registro(
        id=l["id"], criado_em=l["criado_em"], reter_ate=l["reter_ate"], sha256_planilha=l["sha256_planilha"],
        bytes=l["bytes"], estado=l["estado"], parecer=l["parecer"],
        resultado=None if l["resultado_json"] is None else json.loads(l["resultado_json"]),
        erros=None if l["erros_json"] is None else json.loads(l["erros_json"]),
        token=l["token"], sha256_pdf=l["sha256_pdf"], id_original=l["id_original"], duracao_ms=l["duracao_ms"])
