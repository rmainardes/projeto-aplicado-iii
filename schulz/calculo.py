"""Motor de cálculo metrológico — porta de ``nucleo/.../dominio`` (Java).

Equações, para um ponto com n leituras L1..Ln, valor de referência VR e tolerância (Tol+, Tol−):

- média            x̄ = (L1 + … + Ln) / n, com 10 casas decimais, arredondamento HALF_EVEN;
- erro sistemático E = x̄ − VR (com sinal; subtração exata);
- LEA              LEA = Tol+ (bilateral simétrica Tol− = −Tol+, ou unilateral Tol− = 0);
- status           |E| ≤ LEA → DENTRO_DA_TOLERANCIA; senão FORA_DA_TOLERANCIA (a fronteira é dentro);
- parecer          APROVADO se todos os pontos estão dentro; REPROVADO se algum está fora.

Tudo em ``decimal.Decimal``: nada passa por ``float`` depois da leitura da célula, e a comparação com
o LEA é feita sem arredondamento prévio (arredondar a média antes reprovaria/aprovaria errado na
fronteira — cenário ``ok-arredondamento``). Cinco casas só na exibição.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

DENTRO_DA_TOLERANCIA = "DENTRO_DA_TOLERANCIA"
FORA_DA_TOLERANCIA = "FORA_DA_TOLERANCIA"
APROVADO = "APROVADO"
REPROVADO = "REPROVADO"

MINIMO_LEITURAS = 2
ESCALA_MEDIA = Decimal("1E-10")
CASAS_EXIBICAO = Decimal("1E-5")


@dataclass(frozen=True)
class PontoEnsaio:
    """Uma característica medida. O construtor repete R13–R15 (defesa em profundidade)."""

    caracteristica: str
    valor_referencia: Decimal
    tol_superior: Decimal
    tol_inferior: Decimal
    leituras: tuple[Decimal, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.caracteristica or not self.caracteristica.strip():
            raise ValueError("A característica não pode estar em branco.")
        if len(self.leituras) < MINIMO_LEITURAS:
            raise ValueError(f"'{self.caracteristica}': são necessárias pelo menos {MINIMO_LEITURAS} leituras.")
        if self.tol_superior <= 0:
            raise ValueError(f"'{self.caracteristica}': a tolerância superior precisa ser maior que zero.")
        if not (self.simetrica or self.unilateral):
            raise ValueError(f"'{self.caracteristica}': tolerância fora do escopo do MVP.")
        if self.unilateral and any(l < 0 for l in self.leituras):
            raise ValueError(f"'{self.caracteristica}': leitura negativa em característica unilateral.")

    @property
    def lea(self) -> Decimal:
        """Limite de erro admissível: LEA = Tol+ nos dois tipos de tolerância aceitos."""
        return self.tol_superior

    @property
    def simetrica(self) -> bool:
        return self.tol_inferior == -self.tol_superior

    @property
    def unilateral(self) -> bool:
        return self.tol_inferior == 0


def media(leituras: tuple[Decimal, ...] | list[Decimal]) -> Decimal:
    """Média aritmética com 10 casas, HALF_EVEN (sem viés; IEEE 754 e ABNT NBR 5891)."""
    if not leituras:
        raise ValueError("A média precisa de pelo menos uma leitura.")
    with localcontext() as ctx:
        # Precisão folgada: a soma de leituras de até ~15 dígitos e a divisão por n ficam exatas
        # até muito além da 10ª casa, então o quantize é o único arredondamento (como no Java).
        ctx.prec = 60
        soma = sum(leituras, Decimal(0))
        return (soma / Decimal(len(leituras))).quantize(ESCALA_MEDIA, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True)
class ResultadoPonto:
    ponto: PontoEnsaio
    media: Decimal

    @property
    def erro_sistematico(self) -> Decimal:
        with localcontext() as ctx:
            ctx.prec = 60
            return self.media - self.ponto.valor_referencia

    @property
    def status(self) -> str:
        return DENTRO_DA_TOLERANCIA if abs(self.erro_sistematico) <= self.ponto.lea else FORA_DA_TOLERANCIA


@dataclass(frozen=True)
class ResultadoCalibracao:
    pontos: tuple[ResultadoPonto, ...]

    def __post_init__(self) -> None:
        # Ausência de evidência não vira aprovação: all() de lista vazia é True.
        if not self.pontos:
            raise ValueError("A calibração precisa de pelo menos um ponto.")

    @property
    def parecer(self) -> str:
        return APROVADO if all(p.status == DENTRO_DA_TOLERANCIA for p in self.pontos) else REPROVADO


def calcular(pontos: list[PontoEnsaio]) -> ResultadoCalibracao:
    """Um resultado por ponto, na ordem da planilha."""
    return ResultadoCalibracao(tuple(ResultadoPonto(p, media(p.leituras)) for p in pontos))


def exibir(valor: Decimal) -> str:
    """Cinco casas, só para exibição; o valor calculado não é alterado."""
    return format(valor.quantize(CASAS_EXIBICAO, rounding=ROUND_HALF_EVEN), "f")


def texto_plano(valor: Decimal) -> str:
    """Equivalente ao ``toPlainString`` do Java: sem notação científica."""
    return format(valor, "f")
