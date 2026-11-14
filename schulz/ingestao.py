"""Módulo de ingestão — leitura e validação da planilha ``.xlsx`` contra o contrato R01–R15.

Porta de ``nucleo/.../ingestao/LeitorPlanilhaPoi.java``. Erro de arquivo ou de estrutura (R01–R09)
interrompe a leitura com um erro só, porque sem a aba ou o cabeçalho não há o que ler. Os erros de
linha (R10–R15) são todos coletados e devolvidos juntos, para o operador corrigir de uma vez.

Ordem do processamento:
1. Arquivo: tamanho (R01), assinatura zip e pacote OOXML (R02), formato Strict (R03), limites de
   descompactação contra *zip bomb* (R02, D-013).
2. Estrutura: aba ``Medicoes`` (R04), cabeçalhos obrigatórios (R05), ≥ 2 colunas ``Leitura<n>``
   (R06), sem coluna ``Desvio`` (R07).
3. Linhas: higienização do texto e dos nulos (``higienizacao``), obrigatórios (R10), números
   digitados como número e sem fórmula (R11), característica única (R12), tolerância (R13, R14) e
   leitura não negativa em unilateral (R15). Linhas vazias são puladas; nenhuma linha → R08;
   mais de 10 mil → R09.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .calculo import PontoEnsaio, texto_plano
from .higienizacao import limpar_texto, vazio

ABA = "Medicoes"
CARACTERISTICA = "Caracteristica"
VALOR_REFERENCIA = "ValorReferencia"
TOL_SUPERIOR = "ToleranciaSuperior"
TOL_INFERIOR = "ToleranciaInferior"
DESVIO = "Desvio"
OBRIGATORIOS = (CARACTERISTICA, VALOR_REFERENCIA, TOL_SUPERIOR, TOL_INFERIOR)
LEITURA = re.compile(r"Leitura\d+")

MAXIMO_BYTES = 5 * 1024 * 1024
MAXIMO_LINHAS = 10_000
TETO_LINHAS_REGISTRADAS = 100_000
MAXIMO_ENTRADA_ZIP = 50 * 1024 * 1024
TAXA_MINIMA_COMPRESSAO = 0.01  # mesma do ZipSecureFile do POI (100×)
CARENCIA_TAXA = 100 * 1024  # entradas pequenas não passam pelo teste de taxa

ASSINATURA_ZIP = b"PK\x03\x04"
RELACAO_STRICT = b"purl.oclc.org/ooxml/officeDocument/relationships/officeDocument"

MENSAGEM_R02 = "O arquivo não está em formato xlsx. Salve como 'Pasta de Trabalho do Excel (.xlsx)'."
MENSAGEM_R09 = "A planilha excede o limite de 10 mil linhas."


@dataclass(frozen=True)
class ErroValidacao:
    """Um erro do contrato. ``linha`` no padrão do Excel (cabeçalho = 1); ``None`` em erro geral."""

    linha: int | None
    coluna: str | None
    regra: str
    mensagem: str

    def como_dict(self) -> dict[str, Any]:
        return {"linha": self.linha, "coluna": self.coluna, "regra": self.regra, "mensagem": self.mensagem}


class PlanilhaInvalida(Exception):
    """Planilha fora do contrato; carrega todos os erros encontrados."""

    def __init__(self, erros: list[ErroValidacao]):
        super().__init__(f"{len(erros)} erro(s) de validação")
        self.erros = list(erros)


def _geral(regra: str, mensagem: str) -> PlanilhaInvalida:
    return PlanilhaInvalida([ErroValidacao(None, None, regra, mensagem)])


def ler(conteudo: bytes) -> list[PontoEnsaio]:
    """Valida e lê a planilha; devolve os pontos ou lança :class:`PlanilhaInvalida`."""
    if len(conteudo) > MAXIMO_BYTES:
        raise _geral("R01", "O arquivo excede o limite de 5 MB.")
    # R02 pelo conteúdo, não pela extensão: um .xlsx é um zip e começa com "PK".
    if not conteudo.startswith(ASSINATURA_ZIP):
        raise _geral("R02", MENSAGEM_R02)
    _conferir_pacote(conteudo)
    return _ler_pasta(conteudo)


def _conferir_pacote(conteudo: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as pacote:
            nomes = set(pacote.namelist())
            if "[Content_Types].xml" not in nomes or "_rels/.rels" not in nomes:
                raise _geral("R02", MENSAGEM_R02)
            for info in pacote.infolist():
                # D-013: cada entrada descompactada limitada a 50 MB, e taxa de compressão até 100×.
                if info.file_size > MAXIMO_ENTRADA_ZIP:
                    raise _geral("R02", MENSAGEM_R02)
                if info.file_size > CARENCIA_TAXA and info.compress_size / info.file_size < TAXA_MINIMA_COMPRESSAO:
                    raise _geral("R02", MENSAGEM_R02)
            if RELACAO_STRICT in pacote.read("_rels/.rels"):
                raise _geral("R03", "O arquivo está em formato OOXML Strict. "
                                    "Salve como 'Pasta de Trabalho do Excel (.xlsx)'.")
    except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, ValueError, OSError):
        # Zip corrompido ou cortado.
        raise _geral("R02", MENSAGEM_R02) from None


def _ler_pasta(conteudo: bytes) -> list[PontoEnsaio]:
    # Import tardio: o resto do módulo (e os testes de arquivo) não depende do openpyxl.
    import openpyxl

    try:
        pasta = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=False)
    except PlanilhaInvalida:
        raise
    except Exception:  # noqa: BLE001 — qualquer falha do parser num pacote zip é arquivo inválido (R02)
        raise _geral("R02", MENSAGEM_R02) from None
    try:
        if ABA not in pasta.sheetnames:
            raise _geral("R04", "A planilha fornecida não contém a aba Medicoes.")
        aba = pasta[ABA]
        if (aba.max_row or 0) > TETO_LINHAS_REGISTRADAS:
            raise _geral("R09", MENSAGEM_R09)
        linhas = aba.iter_rows()
        primeira = next(linhas, ())
        cabecalho = _ler_cabecalho(primeira)
        return _ler_linhas(linhas, cabecalho)
    except PlanilhaInvalida:
        raise
    except Exception:  # noqa: BLE001 — XML malformado dentro de um pacote válido
        raise _geral("R02", MENSAGEM_R02) from None
    finally:
        pasta.close()


@dataclass(frozen=True)
class _Cabecalho:
    colunas: dict[str, int]  # nome higienizado → índice (0-based)
    leituras: tuple[str, ...]


def _ler_cabecalho(celulas: tuple) -> _Cabecalho:
    colunas: dict[str, int] = {}
    leituras: list[str] = []
    for indice, celula in enumerate(celulas):
        if vazio(celula.value):
            continue
        nome = limpar_texto(_texto_formatado(celula))
        colunas[nome] = indice
        if LEITURA.fullmatch(nome):
            leituras.append(nome)
    for obrigatorio in OBRIGATORIOS:
        if obrigatorio not in colunas:
            raise PlanilhaInvalida([ErroValidacao(None, obrigatorio, "R05",
                                                  f"O cabeçalho {obrigatorio} não consta na planilha fornecida.")])
    if len(leituras) < 2:
        raise _geral("R06", "A planilha fornecida não contém duas séries de medições "
                            "com cabeçalho Leitura* (Leitura1, Leitura2).")
    if DESVIO in colunas:
        raise _geral("R07", "A planilha contém a coluna Desvio, que não é utilizada "
                            "neste cálculo. Remova a coluna e carregue novamente o arquivo.")
    return _Cabecalho(colunas, tuple(leituras))


def _ler_linhas(linhas, cabecalho: _Cabecalho) -> list[PontoEnsaio]:
    coleta = _Coleta(cabecalho)
    pontos: list[PontoEnsaio] = []
    primeira_linha: dict[str, int] = {}
    linhas_de_dados = 0
    for n, celulas in enumerate(linhas, start=2):  # n no padrão do Excel
        if n > TETO_LINHAS_REGISTRADAS + 1:
            raise _geral("R09", MENSAGEM_R09)
        coleta.linha_atual = celulas
        if coleta.linha_vazia():
            continue
        linhas_de_dados += 1
        if linhas_de_dados > MAXIMO_LINHAS:
            raise _geral("R09", MENSAGEM_R09)
        erros_antes = len(coleta.erros)

        caracteristica = coleta.texto(n, CARACTERISTICA)
        referencia = coleta.numero(n, VALOR_REFERENCIA)
        leituras = {nome: coleta.numero(n, nome) for nome in cabecalho.leituras}
        tol_superior = coleta.numero(n, TOL_SUPERIOR)
        tol_inferior = coleta.numero(n, TOL_INFERIOR)
        # R13–R15 precisam de todos os valores: com célula ausente ou inválida, ficam para depois.
        celulas_validas = len(coleta.erros) == erros_antes

        if caracteristica is not None:
            anterior = primeira_linha.setdefault(caracteristica, n)
            if anterior != n:
                coleta.erro(n, CARACTERISTICA, "R12",
                            f"Característica '{caracteristica}' repetida nas linhas {anterior} e {n}.")
        if celulas_validas:
            coleta.regras_de_tolerancia(n, caracteristica, tol_superior, tol_inferior, leituras)
        if len(coleta.erros) == erros_antes:
            pontos.append(PontoEnsaio(caracteristica, referencia, tol_superior, tol_inferior,
                                      tuple(leituras.values())))
    if coleta.erros:
        raise PlanilhaInvalida(coleta.erros)
    if not pontos:
        raise _geral("R08", "A planilha fornecida não contém dados.")
    return pontos


class _Coleta:
    """Lê as células de uma linha registrando os erros em vez de lançar."""

    def __init__(self, cabecalho: _Cabecalho):
        self.cabecalho = cabecalho
        self.erros: list[ErroValidacao] = []
        self.linha_atual: tuple = ()

    def erro(self, linha: int, coluna: str, regra: str, mensagem: str) -> None:
        self.erros.append(ErroValidacao(linha, coluna, regra, mensagem))

    def _celula(self, coluna: str):
        """A célula da coluna, ou ``None`` se ausente, em branco ou só com espaços (nulo)."""
        indice = self.cabecalho.colunas[coluna]
        if indice >= len(self.linha_atual):
            return None
        celula = self.linha_atual[indice]
        return None if vazio(celula.value) else celula

    def linha_vazia(self) -> bool:
        """Sem nada nas colunas do cabeçalho: sobra de formatação no Excel, não conta como dado."""
        return all(self._celula(nome) is None for nome in self.cabecalho.colunas)

    def texto(self, n: int, coluna: str) -> str | None:
        celula = self._celula(coluna)
        if celula is None:
            self._obrigatorio(n, coluna)
            return None
        return limpar_texto(_texto_formatado(celula))

    def numero(self, n: int, coluna: str) -> Decimal | None:
        celula = self._celula(coluna)
        if celula is None:
            self._obrigatorio(n, coluna)
            return None
        if celula.data_type == "f":
            # Valor calculado não entra, nem em cache: pode estar desatualizado ou ausente.
            self.erro(n, coluna, "R11", f"Linha {n}, coluna {coluna}: contém fórmula; digite o valor medido.")
            return None
        valor = celula.value
        if celula.data_type != "n" or isinstance(valor, bool) or not isinstance(valor, (int, float)):
            # Texto, booleano, erro ou data: o contrato pede número digitado.
            self.erro(n, coluna, "R11",
                      f"Linha {n}, coluna {coluna}: '{limpar_texto(_texto_formatado(celula))}' "
                      "não é um número válido.")
            return None
        return _decimal(valor)

    def regras_de_tolerancia(self, n: int, nome: str, tol_superior: Decimal, tol_inferior: Decimal,
                             leituras: dict[str, Decimal]) -> None:
        if tol_superior <= 0:
            self.erro(n, TOL_SUPERIOR, "R13",
                      f"Linha {n} ('{nome}'): a tolerância superior precisa ser maior que zero.")
            return
        simetrica = tol_inferior == -tol_superior
        unilateral = tol_inferior == 0
        if not simetrica and not unilateral:
            self.erro(n, TOL_INFERIOR, "R14",
                      f"Linha {n} ('{nome}'): tolerância +{texto_plano(tol_superior)}/{texto_plano(tol_inferior)} "
                      "fora do escopo do MVP — aceitas: bilateral simétrica ou unilateral.")
            return
        if unilateral:
            # Um erro por leitura negativa: o operador corrige todas de uma vez.
            for coluna, valor in leituras.items():
                if valor < 0:
                    self.erro(n, coluna, "R15",
                              f"Linha {n} ('{nome}'): leitura negativa em característica unilateral "
                              "— verifique a medição.")

    def _obrigatorio(self, n: int, coluna: str) -> None:
        self.erro(n, coluna, "R10", f"Linha {n}, coluna {coluna}: valor obrigatório ausente.")


def _decimal(valor: int | float) -> Decimal:
    """O Excel guarda o double mais próximo (4,14 vira 4.1399999999999997). ``repr`` devolve o
    decimal mais curto que identifica esse double — 4.14 —, como o ``BigDecimal.valueOf`` do Java;
    ``Decimal(float)`` daria a expansão binária inteira."""
    if isinstance(valor, int):
        return Decimal(valor)
    return Decimal(repr(valor))


def _texto_formatado(celula) -> str:
    """Texto da célula como o Excel mostra no formato Geral (equivale ao DataFormatter do POI)."""
    valor = celula.value
    if isinstance(valor, bool):
        return "TRUE" if valor else "FALSE"
    if isinstance(valor, float):
        return str(int(valor)) if valor.is_integer() else format(Decimal(repr(valor)), "f")
    return str(valor)
