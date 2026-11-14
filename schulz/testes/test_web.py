"""API local de ponta a ponta (Flask test client): emissão, idempotência, rejeição, verificação."""

from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from schulz.servico import Configuracao, Servico
from schulz.testes.apoio import planilha
from schulz.web import criar_app

URL_BASE = "http://127.0.0.1:5000"


class ApiTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.servico = Servico(Configuracao(Path(self._tmp.name), URL_BASE, "Operador de Teste"))
        self.cliente = criar_app(self.servico).test_client()

    def tearDown(self):
        self._tmp.cleanup()

    def enviar(self, conteudo: bytes, nome: str = "planilha.xlsx"):
        return self.cliente.post("/api/calibracoes/processamento",
                                 data={"arquivo": (io.BytesIO(conteudo), nome)}, content_type="multipart/form-data")

    def test_emite_certificado_e_verifica_pelo_token(self):
        r = self.enviar(planilha("ok-reprovado.xlsx"))
        self.assertEqual(200, r.status_code)
        c = r.get_json()
        self.assertEqual("EMITIDA", c["estado"])
        self.assertEqual("REPROVADO", c["parecer"])
        self.assertEqual(["DENTRO_DA_TOLERANCIA", "FORA_DA_TOLERANCIA", "DENTRO_DA_TOLERANCIA", "DENTRO_DA_TOLERANCIA"],
                         [p["status"] for p in c["pontos"]])
        self.assertEqual("6.0600000000", c["pontos"][1]["media"], "escala 10 como texto")
        self.assertEqual(hashlib.sha256(planilha("ok-reprovado.xlsx")).hexdigest(), c["sha256Planilha"])

        pdf = self.cliente.get(c["certificado"]["url"])
        self.assertEqual(200, pdf.status_code)
        self.assertEqual("application/pdf", pdf.mimetype)
        self.assertTrue(pdf.data.startswith(b"%PDF-"))
        self.assertEqual(c["certificado"]["sha256Pdf"], hashlib.sha256(pdf.data).hexdigest())

        url = c["certificado"]["urlVerificacao"]
        self.assertTrue(url.startswith(f"{URL_BASE}/verificar/"))
        token = url.rsplit("/", 1)[1]
        v = self.cliente.get(f"/api/verificacao/{token}")
        self.assertEqual(200, v.status_code)
        self.assertEqual({"id", "emitidoEm", "parecer", "sha256Pdf"}, set(v.get_json()), "rota pública mínima")
        self.assertEqual(200, self.cliente.get(f"/verificar/{token}").status_code)

        confere = self.cliente.post(f"/api/verificacao/{token}/conferencia",
                                    data={"arquivo": (io.BytesIO(pdf.data), "c.pdf")},
                                    content_type="multipart/form-data").get_json()
        self.assertTrue(confere["confere"])
        adulterado = pdf.data + b"\n% um byte a mais muda o hash\n"
        confere = self.cliente.post(f"/api/verificacao/{token}/conferencia",
                                    data={"arquivo": (io.BytesIO(adulterado), "c.pdf")},
                                    content_type="multipart/form-data").get_json()
        self.assertFalse(confere["confere"])

    def test_mesmo_arquivo_nao_gera_dois_certificados(self):
        primeiro = self.enviar(planilha("ok-aprovado.xlsx"), "a.xlsx").get_json()
        segundo = self.enviar(planilha("ok-aprovado.xlsx"), "outro-nome.xlsx").get_json()
        self.assertEqual("DUPLICADA", segundo["estado"])
        self.assertEqual(primeiro["id"], segundo["idOriginal"])
        self.assertEqual(1, len(list((Path(self._tmp.name) / "certificados").glob("*.pdf"))))
        ind = self.cliente.get("/api/calibracoes").get_json()["indicadores"]
        self.assertEqual({"envios": 2, "emitidos": 1, "aprovados": 1, "reprovados": 0, "rejeitadas": 0,
                          "duplicadas": 1}, ind)

    def test_planilha_fora_do_contrato_e_400_com_todos_os_erros(self):
        r = self.enviar(planilha("inv-multiplos-erros.xlsx"))
        self.assertEqual(400, r.status_code)
        self.assertEqual("application/problem+json", r.mimetype)
        corpo = r.get_json()
        self.assertEqual("REJEITADA", corpo["estado"])
        self.assertEqual(["R10", "R11", "R14"], [e["regra"] for e in corpo["erros"]])
        # Reenvio da mesma planilha rejeitada é encerrado sem abrir o Excel.
        self.assertEqual("DUPLICADA", self.enviar(planilha("inv-multiplos-erros.xlsx")).get_json()["estado"])

    def test_requisicoes_malformadas(self):
        self.assertEqual(415, self.cliente.post("/api/calibracoes/processamento", json={}).status_code)
        sem_arquivo = self.cliente.post("/api/calibracoes/processamento", data={"x": "1"},
                                        content_type="multipart/form-data")
        self.assertEqual(400, sem_arquivo.status_code)
        self.assertEqual(413, self.enviar(b"PK" + bytes(6 * 1024 * 1024)).status_code)
        self.assertEqual(404, self.cliente.get("/api/verificacao/curto").status_code)
        self.assertEqual(404, self.cliente.get("/api/verificacao/" + "A" * 32).status_code)
        self.assertEqual(404, self.cliente.get("/api/calibracoes/../../etc/passwd/certificado").status_code)
        self.assertEqual(404, self.cliente.get("/api/calibracoes/nao-e-uuid").status_code)
        self.assertEqual(404, self.cliente.get("/api/exemplos/..%2Fpom.xml").status_code)

    def test_nada_de_nome_de_arquivo_no_banco_nem_no_log(self):
        with self.assertLogs("schulz", level="INFO") as logs:
            self.enviar(planilha("ok-limite.xlsx"), "Cliente_Fulano_Matricula_123.xlsx")
        self.assertNotIn("Fulano", "\n".join(logs.output))
        self.assertNotIn("Operador de Teste", "\n".join(logs.output))
        banco = (Path(self._tmp.name) / "calibracoes.db").read_bytes()
        self.assertNotIn(b"Fulano", banco)
        self.assertNotIn(b"Operador de Teste", banco)

    def test_exemplos_e_cabecalhos_de_seguranca(self):
        r = self.cliente.get("/api/exemplos")
        nomes = [e["nome"] for e in r.get_json()["exemplos"]]
        self.assertIn("ok-aprovado.xlsx", nomes)
        self.assertEqual(21, len(nomes))
        self.assertEqual(200, self.cliente.get("/api/exemplos/ok-aprovado.xlsx").status_code)
        pagina = self.cliente.get("/")
        self.assertIn("script-src 'self'", pagina.headers["Content-Security-Policy"])
        self.assertEqual("nosniff", pagina.headers["X-Content-Type-Options"])


if __name__ == "__main__":
    unittest.main()
