"""Contrato da planilha R01–R15 e higienização (docs/av03/contrato-planilha.md)."""

from __future__ import annotations

import io
import unittest
import zipfile

from schulz import ingestao
from schulz.higienizacao import limpar_texto, vazio
from schulz.testes.apoio import CABECALHO, planilha, xlsx

OK = ["Diâmetro eixo", 4.12, 4.13, 4.14, 0.03, -0.03]


def erros(conteudo: bytes) -> list[tuple]:
    with unittest.TestCase().assertRaises(ingestao.PlanilhaInvalida) as ctx:
        ingestao.ler(conteudo)
    return [(e.linha, e.coluna, e.regra) for e in ctx.exception.erros]


class PlanilhasInvalidasDoRepositorioTest(unittest.TestCase):
    ESPERADO = {
        "inv-R02-nao-xlsx.xlsx": [(None, None, "R02")],
        "inv-R03-strict.xlsx": [(None, None, "R03")],
        "inv-R04-sem-aba.xlsx": [(None, None, "R04")],
        "inv-R05-sem-tolsup.xlsx": [(None, "ToleranciaSuperior", "R05")],
        "inv-R06-uma-leitura.xlsx": [(None, None, "R06")],
        "inv-R07-desvio.xlsx": [(None, None, "R07")],
        "inv-R08-vazia.xlsx": [(None, None, "R08")],
        "inv-R10-obrigatorio.xlsx": [(3, "Leitura2", "R10")],
        "inv-R11-texto.xlsx": [(2, "Leitura1", "R11")],
        "inv-R12-repetida.xlsx": [(5, "Caracteristica", "R12")],
        "inv-R13-tolsup-zero.xlsx": [(4, "ToleranciaSuperior", "R13")],
        "inv-R14-assimetrica.xlsx": [(2, "ToleranciaInferior", "R14")],
        "inv-R15-negativa-unilateral.xlsx": [(5, "Leitura1", "R15")],
        "inv-multiplos-erros.xlsx": [(2, "Leitura2", "R10"), (3, "Leitura1", "R11"), (4, "ToleranciaInferior", "R14")],
    }

    def test_cada_planilha_invalida_cai_na_sua_regra(self):
        for arquivo, esperado in self.ESPERADO.items():
            with self.subTest(arquivo=arquivo):
                self.assertEqual(esperado, erros(planilha(arquivo)))

    def test_mensagens_do_contrato(self):
        with self.assertRaises(ingestao.PlanilhaInvalida) as ctx:
            ingestao.ler(planilha("inv-R14-assimetrica.xlsx"))
        self.assertEqual("Linha 2 ('Diâmetro eixo'): tolerância +0.05/-0.02 fora do escopo do MVP — "
                         "aceitas: bilateral simétrica ou unilateral.", ctx.exception.erros[0].mensagem)
        with self.assertRaises(ingestao.PlanilhaInvalida) as ctx:
            ingestao.ler(planilha("inv-R12-repetida.xlsx"))
        self.assertEqual("Característica 'Diâmetro eixo' repetida nas linhas 2 e 5.", ctx.exception.erros[0].mensagem)


class ArquivoTest(unittest.TestCase):
    def test_r01_acima_de_5_mb(self):
        self.assertEqual([(None, None, "R01")], erros(b"PK\x03\x04" + bytes(5 * 1024 * 1024)))

    def test_r02_vazio_texto_e_zip_cortado(self):
        self.assertEqual([(None, None, "R02")], erros(b""))
        self.assertEqual([(None, None, "R02")], erros(b"Caracteristica;ValorReferencia\n"))
        bom = planilha("ok-aprovado.xlsx")
        self.assertEqual([(None, None, "R02")], erros(bom[: len(bom) // 2]))

    def test_r02_zip_que_nao_e_pacote_ooxml(self):
        saida = io.BytesIO()
        with zipfile.ZipFile(saida, "w") as z:
            z.writestr("leia-me.txt", "não é planilha")
        self.assertEqual([(None, None, "R02")], erros(saida.getvalue()))

    def test_r02_zip_bomb(self):
        saida = io.BytesIO()
        with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("_rels/.rels", "<Relationships/>")
            z.writestr("xl/worksheets/sheet1.xml", b"\0" * (20 * 1024 * 1024))  # ~1000:1
        self.assertLess(len(saida.getvalue()), 5 * 1024 * 1024)
        self.assertEqual([(None, None, "R02")], erros(saida.getvalue()))


class EstruturaELinhasTest(unittest.TestCase):
    def test_planilha_minima_valida(self):
        pontos = ingestao.ler(xlsx([OK]))
        self.assertEqual(1, len(pontos))
        self.assertEqual("Diâmetro eixo", pontos[0].caracteristica)

    def test_r09_mais_de_10_mil_linhas(self):
        linhas = [[f"P{i}", 1, 1, 1, 0.1, -0.1] for i in range(10_001)]
        self.assertEqual([(None, None, "R09")], erros(xlsx(linhas)))

    def test_10_mil_linhas_e_o_limite_aceito(self):
        linhas = [[f"P{i}", 1, 1, 1, 0.1, -0.1] for i in range(10_000)]
        self.assertEqual(10_000, len(ingestao.ler(xlsx(linhas))))

    def test_r11_formula_booleano_e_numero_digitado_como_texto(self):
        linhas = [
            ["A", 1, "=1+1", 1, 0.1, -0.1],
            ["B", 1, True, 1, 0.1, -0.1],
            ["C", 1, "10,03", 1, 0.1, -0.1],
        ]
        self.assertEqual([(2, "Leitura1", "R11"), (3, "Leitura1", "R11"), (4, "Leitura1", "R11")], erros(xlsx(linhas)))

    def test_r12_e_verificada_mesmo_com_celula_invalida(self):
        linhas = [OK, ["Diâmetro eixo", 4.12, 4.13, None, 0.03, -0.03]]
        self.assertEqual([(3, "Leitura2", "R10"), (3, "Caracteristica", "R12")], erros(xlsx(linhas)))

    def test_r15_um_erro_por_leitura_negativa(self):
        linhas = [["Planicidade", 0, -0.001, -0.002, 0.05, 0]]
        self.assertEqual([(2, "Leitura1", "R15"), (2, "Leitura2", "R15")], erros(xlsx(linhas)))

    def test_cabecalho_ausente_e_desvio(self):
        self.assertEqual([(None, "ValorReferencia", "R05")],
                         erros(xlsx([], cabecalho=["Caracteristica", "Leitura1", "Leitura2",
                                                   "ToleranciaSuperior", "ToleranciaInferior"])))
        self.assertEqual([(None, None, "R07")], erros(xlsx([OK + [0.01]], cabecalho=CABECALHO + ["Desvio"])))

    def test_leitura_precisa_de_numero_no_nome(self):
        cab = ["Caracteristica", "ValorReferencia", "Leitura1", "LeituraX", "ToleranciaSuperior", "ToleranciaInferior"]
        self.assertEqual([(None, None, "R06")], erros(xlsx([OK], cabecalho=cab)))


class HigienizacaoTest(unittest.TestCase):
    def test_limpar_texto(self):
        self.assertEqual("Diâmetro eixo", limpar_texto("  Diâmetro  eixo​\t"))
        self.assertEqual("Furo A", limpar_texto("﻿Furo\x07 A"))
        self.assertEqual("", limpar_texto("​  "))

    def test_vazio(self):
        self.assertTrue(vazio(None))
        self.assertTrue(vazio("   "))
        self.assertTrue(vazio(" ​"))
        self.assertFalse(vazio(0))
        self.assertFalse(vazio(" x "))

    def test_linha_em_branco_e_pulada_e_espacos_viram_nulo(self):
        linhas = [OK, [None, None, None, None, None, None], ["  ", " ", " ", "", None, None],
                  ["Cpto eixo", 2.83, 2.8299, 2.8302, 0.004, -0.004]]
        self.assertEqual(2, len(ingestao.ler(xlsx(linhas))))
        self.assertEqual([(2, "Leitura1", "R10")], erros(xlsx([["A", 1, "   ", 1, 0.1, -0.1]])))

    def test_caracteristica_e_cabecalho_higienizados(self):
        cab = ["﻿Caracteristica ", " ValorReferencia", "Leitura1", "Leitura2​",
               "ToleranciaSuperior", "ToleranciaInferior "]
        linhas = [["Diâmetro  eixo​", 4.12, 4.13, 4.14, 0.03, -0.03],
                  ["Diâmetro eixo", 4.12, 4.13, 4.14, 0.03, -0.03]]
        # Depois da higienização os dois nomes são iguais: R12 pega a repetição disfarçada.
        self.assertEqual([(3, "Caracteristica", "R12")], erros(xlsx(linhas, cabecalho=cab)))

    def test_numero_preserva_o_decimal_digitado(self):
        ponto = ingestao.ler(xlsx([["A", 4.12, 4.13, 4.14, 0.03, -0.03]]))[0]
        self.assertEqual(["4.13", "4.14"], [str(l) for l in ponto.leituras])  # não 4.1399999999999997


if __name__ == "__main__":
    unittest.main()
