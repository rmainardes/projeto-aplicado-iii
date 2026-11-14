"""Emissão do certificado de calibração em PDF, com QR Code de verificação.

Porta de ``funcoes/.../certificado/GeradorCertificado.java`` (mesmo layout simplificado): cabeçalho
com identificador, data de emissão, autor e SHA-256 da planilha; tabela por ponto; faixa do parecer
(verde ``APROVADO``, vermelho ``REPROVADO``, texto branco legível também em P&B); bloco de
verificação com o token, a URL e o QR Code que aponta para ``/verificar/<token>``.

Só desenha: o cálculo vem pronto de :mod:`schulz.calculo`. Números com 5 casas só na exibição; as
leituras saem como foram lidas. Não registra nada em log nem recebe nome de arquivo (LGPD).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import segno
from fpdf import FPDF

from .calculo import APROVADO, ResultadoCalibracao, exibir, texto_plano

RODAPE = "Documento gerado por PoC acadêmica (UniSENAI, Projeto Aplicado III) — sem validade metrológica"

try:
    FUSO = ZoneInfo("America/Sao_Paulo")
except Exception:  # noqa: BLE001 — Windows sem o pacote tzdata: UTC-3 fixo (sem horário de verão desde 2019)
    from datetime import timedelta, timezone

    FUSO = timezone(timedelta(hours=-3), "America/Sao_Paulo")

MARGEM = 40.0
LINHA = 12.0
TAMANHO = 9.0
QR_LADO = 90.0
TITULOS = ("Característica", "Leituras", "Referência", "Média", "Erro", "LEA", "Status")
LARGURAS = (70.0, 115.0, 60.0, 50.0, 50.0, 40.0, 130.0)  # somam 515 = A4 − 2 margens


@dataclass(frozen=True)
class DadosCertificado:
    id: str
    emitido_em: datetime
    sha256_planilha: str
    gerado_por: str
    resultado: ResultadoCalibracao
    token: str
    url_verificacao: str


def gerar(d: DadosCertificado) -> bytes:
    pdf = FPDF(orientation="P", unit="pt", format="A4")
    # Fontes padrão do PDF em WinAnsi (cp1252), como no PDFBox: cobre acentos, "—" e "ç".
    pdf.core_fonts_encoding = "windows-1252"
    pdf.set_auto_page_break(False)
    pdf.set_margins(MARGEM, MARGEM, MARGEM)
    pdf.set_title(f"Certificado de calibração {d.id}")
    pdf.set_producer("PoC acadêmica - Projeto Aplicado III")
    pdf.set_creator("schulz (versão local Python)")
    _Desenho(pdf, d).desenhar()
    return bytes(pdf.output())


def _codificavel(s: str) -> str:
    """As fontes padrão do PDF cobrem só WinAnsi (cp1252): caractere fora vira ``?`` em vez de
    derrubar a emissão (nome com caractere raro, por exemplo)."""
    return s.encode("cp1252", errors="replace").decode("cp1252")


class _Desenho:
    """Estado de desenho: página corrente, posição vertical (de cima para baixo) e quebra de página."""

    def __init__(self, pdf: FPDF, d: DadosCertificado):
        self.pdf = pdf
        self.d = d
        self.y = 0.0
        self.largura_pagina = pdf.w
        self.altura_pagina = pdf.h

    def desenhar(self) -> None:
        self._nova_pagina()
        self._cabecalho()
        self._tabela()
        self._parecer()
        self._verificacao()

    # --- blocos -------------------------------------------------------------------------------

    def _cabecalho(self) -> None:
        self._texto("B", 16, MARGEM, "Certificado de Calibração")
        self.y += 22
        self._linha(f"Identificador: {self.d.id}")
        emitido = self.d.emitido_em.astimezone(FUSO).strftime("%d/%m/%Y %H:%M:%S")
        self._linha(f"Emitido em: {emitido} (America/Sao_Paulo)")
        self._linha(f"Gerado por: {self.d.gerado_por}")
        self._linha("SHA-256 da planilha de origem:")
        self._linha(self.d.sha256_planilha)
        self.y += 8

    def _tabela(self) -> None:
        self._linha_tabela(TITULOS, "B")
        for r in self.d.resultado.pontos:
            leituras = "; ".join(texto_plano(l) for l in r.ponto.leituras)
            self._linha_tabela((
                r.ponto.caracteristica, leituras, exibir(r.ponto.valor_referencia), exibir(r.media),
                exibir(r.erro_sistematico), exibir(r.ponto.lea), r.status), "")
        self.y += 10

    def _parecer(self) -> None:
        self._garantir_espaco(40)
        parecer = self.d.resultado.parecer
        altura = 30.0
        # Verde-escuro para APROVADO, vermelho-escuro para REPROVADO (mesmas cores do Java).
        if parecer == APROVADO:
            self.pdf.set_fill_color(26, 115, 38)
        else:
            self.pdf.set_fill_color(179, 26, 38)
        self.pdf.rect(MARGEM, self.y - 8, self.largura_pagina - 2 * MARGEM, altura, style="F")
        self.pdf.set_text_color(255, 255, 255)
        self._texto("B", 14, MARGEM + 10, f"PARECER: {parecer}", self.y + 12)
        self.pdf.set_text_color(0, 0, 0)
        self.y += altura + 16

    def _verificacao(self) -> None:
        self._garantir_espaco(QR_LADO + 20)
        self._texto("B", 10, MARGEM, "Verificação de autenticidade")
        self.y += 14
        topo = self.y
        self._linha(f"Token: {self.d.token}")
        largura_util = self.largura_pagina - 2 * MARGEM - QR_LADO - 20
        for parte in self._quebrar(self.d.url_verificacao, largura_util, "", 10):
            self._linha(parte)
        self._qr(self.largura_pagina - MARGEM - QR_LADO, topo - 8)
        self.y = max(self.y, topo + QR_LADO) + 8

    def _qr(self, x: float, y: float) -> None:
        """Desenha a matriz do QR Code como retângulos (sem imagem): nível M, margem de 1 módulo."""
        qr = segno.make(self.d.url_verificacao, error="m", micro=False, boost_error=False)
        matriz = [list(linha) for linha in qr.matrix]
        borda = 1
        lado = len(matriz) + 2 * borda
        modulo = QR_LADO / lado
        self.pdf.set_fill_color(0, 0, 0)
        for i, linha in enumerate(matriz):
            for j, ligado in enumerate(linha):
                if ligado:
                    self.pdf.rect(x + (j + borda) * modulo, y + (i + borda) * modulo, modulo, modulo, style="F")

    # --- primitivas ---------------------------------------------------------------------------

    def _linha_tabela(self, celulas: tuple[str, ...], estilo: str) -> None:
        quebradas = [self._quebrar(c, LARGURAS[i] - 6, estilo, TAMANHO) for i, c in enumerate(celulas)]
        linhas = max(len(q) for q in quebradas)
        altura = linhas * LINHA + 4
        self._garantir_espaco(altura)
        x = MARGEM
        self.pdf.set_draw_color(153, 153, 153)
        topo = self.y - LINHA + 2
        for i, partes in enumerate(quebradas):
            self.pdf.rect(x, topo, LARGURAS[i], altura)
            ty = self.y + 2
            for parte in partes:
                self._texto(estilo, TAMANHO, x + 3, parte, ty)
                ty += LINHA
            x += LARGURAS[i]
        self.y += altura

    def _linha(self, s: str) -> None:
        self._texto("", 10, MARGEM, s)
        self.y += LINHA + 1

    def _texto(self, estilo: str, tamanho: float, x: float, s: str, y: float | None = None) -> None:
        self.pdf.set_font("Helvetica", estilo, tamanho)
        self.pdf.text(x, self.y if y is None else y, _codificavel(s))

    def _quebrar(self, s: str, largura: float, estilo: str, tamanho: float) -> list[str]:
        """Quebra por palavras e, se uma palavra sozinha não couber (hash, URL), por caracteres."""
        self.pdf.set_font("Helvetica", estilo, tamanho)
        linhas: list[str] = []
        atual = ""
        for c in _codificavel(s):
            candidata = atual + c
            if atual and self.pdf.get_string_width(candidata) > largura:
                espaco = atual.rfind(" ")
                if c != " " and espaco > 0:
                    linhas.append(atual[:espaco])
                    atual = atual[espaco + 1:]
                else:
                    linhas.append(atual)
                    atual = ""
            if not (atual == "" and c == " "):
                atual += c
        if atual or not linhas:
            linhas.append(atual)
        return linhas

    def _garantir_espaco(self, altura: float) -> None:
        if self.y + altura > self.altura_pagina - MARGEM - 20:
            self._nova_pagina()

    def _nova_pagina(self) -> None:
        self.pdf.add_page()
        self.y = MARGEM + 10
        self.pdf.set_text_color(89, 89, 89)
        self._texto("", 7.5, MARGEM, RODAPE, self.altura_pagina - MARGEM + 14)
        self.pdf.set_text_color(0, 0, 0)
