"""Higienização de texto e tratamento de nulos da planilha de entrada.

Regras (D-028):

- Texto (característica e cabeçalhos): Unicode NFC; caracteres de controle (Cc) e de formatação
  invisíveis (Cf: zero-width, BOM, marcas de direção) removidos; espaços especiais (NBSP, espaço
  fino…) viram espaço comum; espaços repetidos colapsam em um; bordas aparadas.
- Nulo: célula ausente, ``None``, texto vazio ou só com espaços/invisíveis é tratada como vazia
  (R10 se a coluna for obrigatória; linha inteira vazia é pulada).
- Número: **não** é higienizado. Texto que parece número ("10,03") continua sendo R11, como no
  contrato: o separador decimal seria ambíguo e corrigir em silêncio esconderia erro de digitação.
"""

from __future__ import annotations

import re
import unicodedata

_ESPACOS = re.compile(r"\s+")


def limpar_texto(valor: str) -> str:
    """Devolve o texto higienizado; pode devolver ``""`` (que o leitor trata como nulo)."""
    normalizado = unicodedata.normalize("NFC", valor)
    partes = []
    for c in normalizado:
        categoria = unicodedata.category(c)
        if categoria == "Zs" or c in "\t\n\r\f\v":
            partes.append(" ")
        elif categoria in ("Cc", "Cf"):
            continue
        else:
            partes.append(c)
    return _ESPACOS.sub(" ", "".join(partes)).strip()


def vazio(valor: object) -> bool:
    """``True`` para célula sem conteúdo útil: ``None`` ou texto que some na higienização."""
    if valor is None:
        return True
    if isinstance(valor, str):
        return limpar_texto(valor) == ""
    return False
