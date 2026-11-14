"""Estudo de ROI da automação (AV05) — premissas explícitas, contas reproduzíveis.

Uso:  python ferramentas/roi.py > docs/av05/roi.md   (tabelas em Markdown, incluídas no relatório da AV05)

Toda conta do relatório sai daqui: se a Schulz informar dados reais (volume, custo-hora, tempos),
basta trocar as premissas e rodar de novo. Só biblioteca padrão; valores em Decimal.

Fórmulas (roteiro da AV05):
    Economia bruta anual (OPEX saved) = horas economizadas × custo-hora + retrabalho evitado
    Economia líquida no horizonte    = (economia bruta − custo operacional) × anos
    ROI %                            = (Economia líquida − Investimento) / Investimento × 100
    Payback (meses)                  = Investimento / (economia líquida anual / 12)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_EVEN, Decimal as D

# --- Etapas do processo (AV01, §1.1.4): minutos por certificado, AS-IS → TO-BE -------------------
# (id, etapa, minutos manual, minutos automatizado, o que muda)
ETAPAS = [
    ("P-06", "Gerar o relatório da MMC no Excel", 1, 1, "mantida: é a origem da planilha"),
    ("P-07", "Digitar metrologista, MMC e fornecedor", 2, 0, "autoria pela autenticação do usuário"),
    ("P-08", "Salvar o relatório como .xlsx", 1, 1, "mantida: salvar no formato do contrato"),
    ("P-09", "Transpor os 28 valores para a planilha de cálculo", 10, 0, "leitura automática (ingestão)"),
    ("P-10", "Informar o padrão por código", 1, 1, "mantida: fora do escopo do MVP"),
    ("P-11", "Digitar temperatura e observações", 2, 2, "mantida: fora do escopo do MVP"),
    ("P-12", "Cálculo nas fórmulas do Excel", 0, 0, "motor validado contra o oráculo"),
    ("P-13", "Conferir valores do certificado contra a MMC", 10, 1, "15 regras validadas pelo sistema; revisão da tela"),
    ("P-14", "Selecionar o signatário pelo índice", 1, 0, "autoria pela autenticação"),
    ("P-15", "Revisar e assinar o certificado", 15, 5, "revisão de layout fixo, sem transcrição a conferir"),
    ("P-16", "Exportar o PDF", 3, 0, "PDF gerado automaticamente"),
    ("P-17", "Lançar resultado no LightLab", 5, 5, "mantida: sem integração (D-002)"),
    ("P-18", "Arquivar planilha e PDF", 2, 0, "armazenado com retenção de 5 anos"),
    ("Novo", "Enviar a planilha e ler o resultado", 0, 1, "upload na interface"),
]
# Etapas que o sistema absorve por completo (transcrição, conferência, cálculo, PDF, arquivo).
BLOCO_AUTOMATIZADO = {"P-07", "P-09", "P-13", "P-14", "P-16", "P-18", "Novo"}


@dataclass(frozen=True)
class Premissas:
    nome: str
    certificados_ano: D  # V — AV01: nº 00091 em 26/08/2026, extrapolado para o ano
    custo_hora_tecnica: D  # C — metrologista, custo carregado (AV01)
    minutos_manual: D  # soma das etapas AS-IS
    minutos_automatizado: D  # soma das etapas TO-BE
    taxa_retrabalho_antes: D  # reemissões por inconsistência (AV01)
    taxa_retrabalho_depois: D  # residual: erro de medição, planilha errada aceita pelo contrato
    fator_custo_reemissao: D  # reemissão = fator × tempo manual × C (reanálise + nova assinatura)
    custo_nuvem_ano: D  # Free Tier / plano gratuito (CT-415) e versão local sem infraestrutura
    manutencao_ano: D  # suporte e pequenas correções
    investimento_economico: D  # quanto custaria contratar o que foi construído
    investimento_desembolso: D  # o que a Schulz efetivamente gasta (PoC feita na parceria acadêmica)


def _minutos(coluna: int, so_bloco: bool = False) -> D:
    return D(sum(e[coluna] for e in ETAPAS if not so_bloco or e[0] in BLOCO_AUTOMATIZADO))


# Investimento — premissas (horas × custo-hora):
HORAS_DESENVOLVIMENTO = D(180)  # AV02 a AV05: arquitetura, núcleo, nuvem, web, versão local, testes, docs
CUSTO_HORA_DESENVOLVEDOR = D(60)  # desenvolvedor júnior, custo carregado
HORAS_VALIDACAO = D(16)  # ISO/IEC 17025 §7.11.2: validar o software de cálculo antes do uso
HORAS_IMPLANTACAO_TREINAMENTO = D(10)  # instalação + 4 metrologistas × 2 h
CUSTO_HORA_METROLOGISTA = D(75)

INVESTIMENTO_DESENVOLVIMENTO = HORAS_DESENVOLVIMENTO * CUSTO_HORA_DESENVOLVEDOR
INVESTIMENTO_VALIDACAO = HORAS_VALIDACAO * CUSTO_HORA_METROLOGISTA
INVESTIMENTO_IMPLANTACAO = HORAS_IMPLANTACAO_TREINAMENTO * CUSTO_HORA_METROLOGISTA
INVESTIMENTO_INFRA = D(0)

BASE = Premissas(
    nome="Base",
    certificados_ano=D(137),
    custo_hora_tecnica=CUSTO_HORA_METROLOGISTA,
    minutos_manual=_minutos(2),
    minutos_automatizado=_minutos(3),
    taxa_retrabalho_antes=D("0.10"),
    taxa_retrabalho_depois=D("0.02"),
    fator_custo_reemissao=D("1.5"),
    custo_nuvem_ano=D(0),
    manutencao_ano=D(24) * CUSTO_HORA_DESENVOLVEDOR,  # 2 h/mês
    investimento_economico=INVESTIMENTO_DESENVOLVIMENTO + INVESTIMENTO_VALIDACAO + INVESTIMENTO_IMPLANTACAO
    + INVESTIMENTO_INFRA,
    investimento_desembolso=INVESTIMENTO_VALIDACAO + INVESTIMENTO_IMPLANTACAO + INVESTIMENTO_INFRA,
)
CONSERVADOR = replace(BASE, nome="Conservador", certificados_ano=D(100), custo_hora_tecnica=D(60),
                      minutos_automatizado=BASE.minutos_automatizado + 5, taxa_retrabalho_antes=D("0.05"))
OTIMISTA = replace(BASE, nome="Otimista (outras famílias de instrumentos)", certificados_ano=D(274),
                   custo_hora_tecnica=D(90), taxa_retrabalho_depois=D("0.01"))
CENARIOS = [CONSERVADOR, BASE, OTIMISTA]


@dataclass(frozen=True)
class Resultado:
    p: Premissas
    horas_manual_ano: D
    horas_automatizado_ano: D
    horas_economizadas_ano: D
    custo_manual_ano: D
    custo_automatizado_ano: D
    ganho_horas_ano: D
    custo_reemissao: D
    ganho_retrabalho_ano: D
    economia_bruta_ano: D
    custo_operacional_ano: D
    economia_liquida_ano: D

    def roi(self, investimento: D, meses: int) -> D:
        economia = self.economia_liquida_ano * D(meses) / D(12)
        return (economia - investimento) / investimento * D(100)

    def payback_meses(self, investimento: D) -> D:
        return investimento / (self.economia_liquida_ano / D(12))


def calcular(p: Premissas) -> Resultado:
    horas_manual = p.certificados_ano * p.minutos_manual / D(60)
    horas_auto = p.certificados_ano * p.minutos_automatizado / D(60)
    custo_reemissao = p.fator_custo_reemissao * p.minutos_manual / D(60) * p.custo_hora_tecnica
    ganho_retrabalho = p.certificados_ano * (p.taxa_retrabalho_antes - p.taxa_retrabalho_depois) * custo_reemissao
    ganho_horas = (horas_manual - horas_auto) * p.custo_hora_tecnica
    bruta = ganho_horas + ganho_retrabalho
    operacional = p.custo_nuvem_ano + p.manutencao_ano
    return Resultado(p, horas_manual, horas_auto, horas_manual - horas_auto, horas_manual * p.custo_hora_tecnica,
                     horas_auto * p.custo_hora_tecnica, ganho_horas, custo_reemissao, ganho_retrabalho, bruta,
                     operacional, bruta - operacional)


def volume_para_payback(p: Premissas, investimento: D, meses: int) -> D:
    """Certificados/ano para pagar o investimento em ``meses``."""
    por_certificado = ((p.minutos_manual - p.minutos_automatizado) / D(60) * p.custo_hora_tecnica
                       + (p.taxa_retrabalho_antes - p.taxa_retrabalho_depois)
                       * p.fator_custo_reemissao * p.minutos_manual / D(60) * p.custo_hora_tecnica)
    return (investimento * D(12) / D(meses) + p.custo_nuvem_ano + p.manutencao_ano) / por_certificado


# --- formatação ---------------------------------------------------------------------------------

def brl(v: D) -> str:
    q = v.quantize(D("0.01"), rounding=ROUND_HALF_EVEN)
    inteiro, _, cent = f"{abs(q):,.2f}".partition(".")
    return f"{'−' if q < 0 else ''}R$ {inteiro.replace(',', '.')},{cent}"


def num(v: D, casas: int = 1) -> str:
    q = v.quantize(D(1).scaleb(-casas), rounding=ROUND_HALF_EVEN)
    texto = f"{abs(q):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'−' if q < 0 else ''}{texto}"


def pct(v: D) -> str:
    return f"{num(v, 1)}%"


def tabelas() -> str:
    b = calcular(BASE)
    linhas: list[str] = ["# Estudo de ROI — tabelas geradas por `python ferramentas/roi.py`", ""]
    w = linhas.append

    w("## Tempo por certificado, etapa a etapa (AV01 §1.1.4)\n")
    w("| Etapa | Atividade | Manual (min) | Automatizado (min) | O que muda |")
    w("| --- | --- | ---: | ---: | --- |")
    for id_, nome, antes, depois, obs in ETAPAS:
        w(f"| {id_} | {nome} | {antes} | {depois} | {obs} |")
    w(f"| **Total** | **Ciclo do certificado** | **{_minutos(2)}** | **{_minutos(3)}** | "
      f"**−{num((1 - _minutos(3) / _minutos(2)) * 100, 0)}%** |")
    w(f"| | Bloco absorvido pelo sistema (transcrição, conferência, cálculo, PDF, arquivo) | "
      f"{_minutos(2, True)} | {_minutos(3, True)} | −{num((1 - _minutos(3, True) / _minutos(2, True)) * 100, 0)}% |")
    w("")

    w("## Premissas operacionais (cenário base)\n")
    w("| Premissa | Valor | Origem |")
    w("| --- | --- | --- |")
    w(f"| Volume de certificados/ano (V) | {BASE.certificados_ano} | AV01: certificado nº 00091 em 26/08/2026, extrapolado [PREMISSA] |")
    w(f"| Tempo manual por certificado | {BASE.minutos_manual} min | AV01, soma de P-06 a P-18 [PREMISSA] |")
    w(f"| Tempo automatizado por certificado | {BASE.minutos_automatizado} min | tabela acima; processamento da máquina < 1 s (§6) |")
    w(f"| Custo da hora técnica (C) | {brl(BASE.custo_hora_tecnica)} | AV01, metrologista com encargos [PREMISSA] |")
    w(f"| Retrabalho (reemissões) antes → depois | {pct(BASE.taxa_retrabalho_antes * 100)} → {pct(BASE.taxa_retrabalho_depois * 100)} | AV01 [PREMISSA]; residual: erro de medição |")
    w(f"| Custo de uma reemissão | {brl(b.custo_reemissao)} | 1,5 × tempo manual × C (AV01) |")
    w(f"| Infraestrutura em nuvem | {brl(BASE.custo_nuvem_ano)}/ano | Free Tier/plano gratuito, US$ 0,00 no Cost Explorer (CT-415); versão local sem servidor |")
    w(f"| Manutenção e suporte | {brl(BASE.manutencao_ano)}/ano | 2 h/mês × {brl(CUSTO_HORA_DESENVOLVEDOR)} [PREMISSA] |")
    w("")

    w("## Investimento\n")
    w("| Item | Cálculo | Valor |")
    w("| --- | --- | ---: |")
    w(f"| Desenvolvimento (AV02–AV05) | {HORAS_DESENVOLVIMENTO} h × {brl(CUSTO_HORA_DESENVOLVEDOR)} | {brl(INVESTIMENTO_DESENVOLVIMENTO)} |")
    w(f"| Validação do software pelo laboratório (ISO/IEC 17025 §7.11.2) | {HORAS_VALIDACAO} h × {brl(CUSTO_HORA_METROLOGISTA)} | {brl(INVESTIMENTO_VALIDACAO)} |")
    w(f"| Implantação e treinamento | {HORAS_IMPLANTACAO_TREINAMENTO} h × {brl(CUSTO_HORA_METROLOGISTA)} | {brl(INVESTIMENTO_IMPLANTACAO)} |")
    w(f"| Infraestrutura (nuvem Free Tier / computador existente) | — | {brl(INVESTIMENTO_INFRA)} |")
    w(f"| **Investimento econômico (como se contratado)** | | **{brl(BASE.investimento_economico)}** |")
    w(f"| **Desembolso efetivo da Schulz** (desenvolvimento feito na parceria acadêmica) | | **{brl(BASE.investimento_desembolso)}** |")
    w("")

    w("## Tabela comparativa: fluxo manual × automatizado (cenário base, por ano)\n")
    w("| Indicador | Manual | Automatizado | Diferença |")
    w("| --- | ---: | ---: | ---: |")
    w(f"| Horas técnicas | {num(b.horas_manual_ano)} h | {num(b.horas_automatizado_ano)} h | **{num(b.horas_economizadas_ano)} h economizadas** |")
    w(f"| Custo das horas técnicas | {brl(b.custo_manual_ano)} | {brl(b.custo_automatizado_ano)} | {brl(b.ganho_horas_ano)} |")
    reem_antes = BASE.certificados_ano * BASE.taxa_retrabalho_antes
    reem_depois = BASE.certificados_ano * BASE.taxa_retrabalho_depois
    w(f"| Reemissões/ano | {num(reem_antes)} | {num(reem_depois)} | {num(reem_antes - reem_depois)} |")
    w(f"| Custo do retrabalho | {brl(reem_antes * b.custo_reemissao)} | {brl(reem_depois * b.custo_reemissao)} | {brl(b.ganho_retrabalho_ano)} |")
    w(f"| Infraestrutura em nuvem | — | {brl(BASE.custo_nuvem_ano)} | — |")
    w(f"| **Economia Bruta Anual (OPEX Saved)** | | | **{brl(b.economia_bruta_ano)}** |")
    w(f"| (−) Manutenção e suporte | | {brl(BASE.manutencao_ano)} | −{brl(BASE.manutencao_ano)} |")
    w(f"| **Economia Líquida Anual** | | | **{brl(b.economia_liquida_ano)}** |")
    w("")

    w("## ROI e payback (cenário base)\n")
    w("ROI % = (Economia Líquida − Investimento) / Investimento × 100, com a economia líquida acumulada no horizonte.\n")
    w("| Visão do investimento | Investimento | ROI 12 meses | ROI 36 meses | ROI 60 meses | Payback |")
    w("| --- | ---: | ---: | ---: | ---: | ---: |")
    for nome, inv in (("Econômico (contratado)", BASE.investimento_economico),
                      ("Desembolso efetivo da Schulz", BASE.investimento_desembolso)):
        w(f"| {nome} | {brl(inv)} | {pct(b.roi(inv, 12))} | {pct(b.roi(inv, 36))} | {pct(b.roi(inv, 60))} | "
          f"{num(b.payback_meses(inv))} meses |")
    w("")
    w("Memória de cálculo (visão econômica, 12 meses): "
      f"({brl(b.economia_liquida_ano)} − {brl(BASE.investimento_economico)}) / {brl(BASE.investimento_economico)} × 100 = "
      f"{pct(b.roi(BASE.investimento_economico, 12))}; payback = {brl(BASE.investimento_economico)} / "
      f"({brl(b.economia_liquida_ano)} / 12) = {num(b.payback_meses(BASE.investimento_economico))} meses.")
    w("")

    w("## Sensibilidade\n")
    w("| Cenário | Certificados/ano | Custo-hora | Min. manual → automatizado | Retrabalho | Economia líquida/ano | Payback (econômico) | ROI 36 m (econômico) | Payback (desembolso) |")
    w("| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |")
    for p in CENARIOS:
        r = calcular(p)
        w(f"| {p.nome} | {p.certificados_ano} | {brl(p.custo_hora_tecnica)} | {p.minutos_manual} → {p.minutos_automatizado} | "
          f"{pct(p.taxa_retrabalho_antes * 100)} → {pct(p.taxa_retrabalho_depois * 100)} | {brl(r.economia_liquida_ano)} | "
          f"{num(r.payback_meses(p.investimento_economico))} meses | {pct(r.roi(p.investimento_economico, 36))} | "
          f"{num(r.payback_meses(p.investimento_desembolso))} meses |")
    w("")
    w(f"Ponto de equilíbrio: com as demais premissas do cenário base, o investimento econômico se paga em 12 meses "
      f"a partir de **{num(volume_para_payback(BASE, BASE.investimento_economico, 12), 0)} certificados/ano**, e em 24 meses "
      f"a partir de **{num(volume_para_payback(BASE, BASE.investimento_economico, 24), 0)}**.")
    return "\n".join(linhas)


if __name__ == "__main__":
    print(tabelas())
