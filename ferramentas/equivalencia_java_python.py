"""Equivalência Java × Python: compara a versão local (Python) com as respostas gravadas da API Java.

Uso (na raiz, com o venv da versão local ativo):
    python ferramentas/equivalencia_java_python.py

Referência: ``docs/av03/evidencias/respostas/*.txt``, as respostas reais do ``app-local`` (Java,
Spring Boot) às 21 planilhas sintéticas, gravadas na AV03 com ``curl -i``. Para cada planilha:

- válida: parecer, e por ponto característica, leituras, referência, média, erro, LEA e status
  (a API Java exibe média e erro com 5 casas; compara-se com a exibição da versão Python);
- inválida: a lista de erros inteira — linha, coluna, regra e mensagem, texto a texto.

Sai com código 1 se houver qualquer divergência.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from schulz import calculo, ingestao  # noqa: E402

RESPOSTAS = RAIZ / "docs" / "av03" / "evidencias" / "respostas"
PLANILHAS = RAIZ / "nucleo" / "src" / "test" / "resources" / "planilhas"


def resposta_java(arquivo: Path) -> dict:
    linha = next(l for l in arquivo.read_text(encoding="utf-8").splitlines() if l.startswith("{"))
    return json.loads(linha, parse_float=Decimal, parse_int=Decimal)


def resposta_python(planilha: Path) -> dict:
    try:
        resultado = calculo.calcular(ingestao.ler(planilha.read_bytes()))
    except ingestao.PlanilhaInvalida as e:
        return {"erros": [x.como_dict() for x in e.erros]}
    return {"parecer": resultado.parecer, "pontos": [{
        "caracteristica": r.ponto.caracteristica,
        "leituras": list(r.ponto.leituras),
        "valorReferencia": r.ponto.valor_referencia,
        "media": Decimal(calculo.exibir(r.media)),
        "erroSistematico": Decimal(calculo.exibir(r.erro_sistematico)),
        "lea": r.ponto.lea,
        "status": r.status,
    } for r in resultado.pontos]}


def comparar(java: dict, python: dict) -> list[str]:
    if "erros" in java or "erros" in python:
        a = [(e["linha"] if e["linha"] is None else int(e["linha"]), e["coluna"], e["regra"], e["mensagem"])
             for e in java.get("erros", [])]
        b = [(e["linha"], e["coluna"], e["regra"], e["mensagem"]) for e in python.get("erros", [])]
        return [] if a == b else [f"erros: Java {a} ≠ Python {b}"]
    diferencas = []
    if java["parecer"] != python["parecer"]:
        diferencas.append(f"parecer: {java['parecer']} ≠ {python['parecer']}")
    if len(java["pontos"]) != len(python["pontos"]):
        return diferencas + ["número de pontos diferente"]
    for i, (pj, pp) in enumerate(zip(java["pontos"], python["pontos"]), start=1):
        for campo in ("caracteristica", "leituras", "valorReferencia", "media", "erroSistematico", "lea", "status"):
            if pj[campo] != pp[campo]:  # Decimal compara valor (10.0 == 10), não escala
                diferencas.append(f"ponto {i} {campo}: {pj[campo]} ≠ {pp[campo]}")
    return diferencas


def main() -> int:
    linhas = ["| Planilha | Resultado Java (AV03) | Resultado Python (AV05) | Equivalente |", "| --- | --- | --- | --- |"]
    falhas = 0
    for arquivo in sorted(RESPOSTAS.glob("*.txt")):
        planilha = PLANILHAS / f"{arquivo.stem}.xlsx"
        java, python = resposta_java(arquivo), resposta_python(planilha)
        diferencas = comparar(java, python)
        falhas += bool(diferencas)

        def resumo(r: dict) -> str:
            if "erros" in r:
                return "rejeitada: " + ", ".join(f"{e['regra']}" + (f" L{int(e['linha'])}" if e["linha"] is not None else "")
                                                 for e in r["erros"])
            return f"{r['parecer']} ({sum(p['status'] == 'FORA_DA_TOLERANCIA' for p in r['pontos'])} de {len(r['pontos'])} fora)"

        linhas.append(f"| `{planilha.name}` | {resumo(java)} | {resumo(python)} | {'não: ' + '; '.join(diferencas) if diferencas else 'sim'} |")
    total = len(linhas) - 2
    print("\n".join(linhas))
    print(f"\n{total - falhas} de {total} planilhas equivalentes.")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
