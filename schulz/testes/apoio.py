"""Apoio dos testes: planilhas sintéticas do repositório e gerador de planilhas em memória."""

from __future__ import annotations

import io
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PLANILHAS = RAIZ / "nucleo" / "src" / "test" / "resources" / "planilhas"
CABECALHO = ["Caracteristica", "ValorReferencia", "Leitura1", "Leitura2", "ToleranciaSuperior", "ToleranciaInferior"]


def planilha(nome: str) -> bytes:
    return (PLANILHAS / nome).read_bytes()


def xlsx(linhas: list[list], cabecalho: list | None = None, aba: str = "Medicoes") -> bytes:
    """Gera um .xlsx Transitional em memória (openpyxl). Valor que começa com '=' vira fórmula."""
    import openpyxl

    pasta = openpyxl.Workbook()
    folha = pasta.active
    folha.title = aba
    folha.append(CABECALHO if cabecalho is None else cabecalho)
    for linha in linhas:
        folha.append(linha)
    saida = io.BytesIO()
    pasta.save(saida)
    return saida.getvalue()
