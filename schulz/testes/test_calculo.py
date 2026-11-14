"""Motor de cálculo contra o oráculo independente (docs/av03/oraculo-planilhas.md)."""

from __future__ import annotations

import unittest
from decimal import Decimal as D

from schulz import calculo, ingestao
from schulz.calculo import APROVADO, DENTRO_DA_TOLERANCIA as DENTRO, FORA_DA_TOLERANCIA as FORA, REPROVADO
from schulz.testes.apoio import planilha

# arquivo → (parecer, [(característica, média, erro, status)]); média e erro com 10 casas, como o Java.
ORACULO = {
    "ok-aprovado.xlsx": (APROVADO, [
        ("Diâmetro eixo", "4.1350000000", "0.0150000000", DENTRO),
        ("Comprimento eixo", "10.8090000000", "0.0090000000", DENTRO),
        ("Largura base", "0.9288000000", "0E-10", DENTRO)]),
    "ok-reprovado.xlsx": (REPROVADO, [
        ("Diâmetro furo A", "6.0150000000", "0.0150000000", DENTRO),
        ("Diâmetro furo B", "6.0600000000", "0.0600000000", FORA),
        ("Altura flange", "25.4000000000", "0E-10", DENTRO),
        ("Planicidade face", "0.0130000000", "0.0130000000", DENTRO)]),
    "ok-limite.xlsx": (APROVADO, [
        ("Comprimento pino", "10.0800000000", "0.0800000000", DENTRO),
        ("Diâmetro bucha", "1.9500000000", "-0.0500000000", DENTRO)]),
    "ok-erro-negativo.xlsx": (APROVADO, [
        ("Diâmetro alojamento", "19.9750000000", "-0.0250000000", DENTRO),
        ("Espessura chapa", "3.4900000000", "-0.0100000000", DENTRO)]),
    "ok-unilateral.xlsx": (REPROVADO, [
        ("Planicidade base", "0.0250000000", "0.0250000000", DENTRO),
        ("Posição furo", "0.1200000000", "0.1200000000", FORA),
        ("Paralelismo face", "0.0020000000", "0.0020000000", DENTRO)]),
    "ok-arredondamento.xlsx": (REPROVADO, [
        ("Diâmetro pino guia", "0.0604500000", "0.0004500000", FORA),
        ("Diâmetro furo guia", "0.0595500000", "-0.0004500000", FORA)]),
    "ok-tres-leituras.xlsx": (REPROVADO, [
        ("Comprimento haste", "10.0166666667", "0.0166666667", DENTRO),
        ("Diâmetro haste", "1.0033333333", "0.0033333333", FORA)]),
}


class OraculoTest(unittest.TestCase):
    def test_as_sete_planilhas_validas_batem_com_o_oraculo(self):
        for arquivo, (parecer, pontos) in ORACULO.items():
            with self.subTest(arquivo=arquivo):
                resultado = calculo.calcular(ingestao.ler(planilha(arquivo)))
                self.assertEqual(parecer, resultado.parecer)
                self.assertEqual(len(pontos), len(resultado.pontos))
                for r, (nome, media, erro, status) in zip(resultado.pontos, pontos):
                    self.assertEqual(nome, r.ponto.caracteristica)
                    self.assertEqual(D(media), r.media)
                    self.assertEqual(str(D(media)), str(r.media), "escala 10 preservada")
                    self.assertEqual(D(erro), r.erro_sistematico)
                    self.assertEqual(status, r.status)


class MediaTest(unittest.TestCase):
    def test_escala_10_half_even(self):
        plano = calculo.texto_plano
        self.assertEqual("10.0166666667", plano(calculo.media([D("10.01"), D("10.02"), D("10.02")])))
        # 0.00000000005 exato na 11ª casa: HALF_EVEN arredonda para o par (0), HALF_UP daria 1.
        self.assertEqual("0.0000000000", plano(calculo.media([D("0.0000000001"), D("0")])))
        self.assertEqual("0.0000000002", plano(calculo.media([D("0.0000000003"), D("0")])))

    def test_sem_leituras_e_erro(self):
        with self.assertRaises(ValueError):
            calculo.media([])

    def test_fronteira_e_dentro_e_nao_passa_por_float(self):
        # Em double, 10.07 + 10.09 = 20.159999999999997: a média sairia abaixo de 10.08 e o erro
        # ficaria a um fio do LEA. Em Decimal, |E| = LEA exatamente → DENTRO.
        p = calculo.PontoEnsaio("x", D("10"), D("0.08"), D("-0.08"), (D("10.07"), D("10.09")))
        r = calculo.calcular([p]).pontos[0]
        self.assertEqual(D("0.08"), r.erro_sistematico)
        self.assertEqual(DENTRO, r.status)

    def test_arredondar_antes_de_comparar_mudaria_o_status(self):
        p = calculo.PontoEnsaio("x", D("0.06"), D("0.0004"), D("-0.0004"), (D("0.0604"), D("0.0605")))
        r = calculo.calcular([p]).pontos[0]
        self.assertEqual(FORA, r.status)  # |E| = 0,00045 > 0,0004
        self.assertEqual("0.00045", calculo.exibir(r.erro_sistematico))


class DominioTest(unittest.TestCase):
    def test_calibracao_sem_pontos_nao_aprova(self):
        with self.assertRaises(ValueError):
            calculo.calcular([])

    def test_ponto_repete_as_regras_do_contrato(self):
        casos = [
            ("", D("1"), D("0.1"), D("-0.1"), (D("1"), D("1"))),        # característica em branco
            ("x", D("1"), D("0.1"), D("-0.1"), (D("1"),)),              # uma leitura
            ("x", D("1"), D("0"), D("0"), (D("1"), D("1"))),            # R13
            ("x", D("1"), D("0.05"), D("-0.02"), (D("1"), D("1"))),     # R14
            ("x", D("0"), D("0.05"), D("0"), (D("-0.01"), D("0.01"))),  # R15
        ]
        for caso in casos:
            with self.subTest(caso=caso), self.assertRaises(ValueError):
                calculo.PontoEnsaio(*caso)

    def test_exibicao_com_cinco_casas(self):
        self.assertEqual("0.00000", calculo.exibir(D("0E-10")))
        self.assertEqual("-0.02500", calculo.exibir(D("-0.0250000000")))
        self.assertEqual("1.00333", calculo.exibir(D("1.0033333333")))


if __name__ == "__main__":
    unittest.main()
