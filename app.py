"""Ponto de entrada da versão local do MVP (AV05) — API backend + interface web.

Uso (o ``iniciar_aplicacao_schulz.bat`` faz isto sozinho):

    python app.py                 # http://127.0.0.1:5000, só nesta máquina
    python app.py --porta 8081    # outra porta
    python app.py --lan           # aceita conexões da rede local; o QR Code usa o IP da máquina,
                                  # para conferir o certificado pelo celular no mesmo Wi-Fi

Variáveis de ambiente (opcionais): SCHULZ_PORTA, SCHULZ_DADOS (pasta do banco SQLite e dos PDFs,
padrão ``dados/``), SCHULZ_URL_BASE (base da URL do QR Code), SCHULZ_OPERADOR (nome no campo
"Gerado por" do PDF; padrão: usuário logado no sistema operacional).
"""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import socket
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

VERSAO_MINIMA = (3, 10)
if sys.version_info < VERSAO_MINIMA:
    sys.exit("Python 3.10 ou superior é necessário (encontrado %d.%d)." % sys.version_info[:2])

from schulz import VERSAO  # noqa: E402
from schulz.servico import Configuracao, Servico  # noqa: E402
from schulz.web import criar_app  # noqa: E402

RAIZ = Path(__file__).resolve().parent


def _ip_da_rede() -> str:
    """IP da interface usada para sair para a rede (nenhum pacote é enviado: UDP só escolhe a rota)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))  # TEST-NET-1 (RFC 5737)
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def _configurar_log(pasta: Path) -> None:
    formato = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    arquivo = RotatingFileHandler(pasta / "schulz.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    arquivo.setFormatter(formato)
    console = logging.StreamHandler()
    console.setFormatter(formato)
    raiz = logging.getLogger("schulz")
    raiz.setLevel(logging.INFO)
    raiz.addHandler(arquivo)
    raiz.addHandler(console)
    # O log de acesso do Werkzeug mostraria o token na URL de verificação: só avisos e erros.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> None:
    argumentos = argparse.ArgumentParser(description="Certificados de calibração — Schulz S.A. (versão local)")
    argumentos.add_argument("--porta", type=int, default=int(os.environ.get("SCHULZ_PORTA", "5000")))
    argumentos.add_argument("--lan", action="store_true",
                            help="escuta em todas as interfaces e usa o IP da rede no QR Code")
    args = argumentos.parse_args(argv)

    pasta_dados = Path(os.environ.get("SCHULZ_DADOS", RAIZ / "dados")).resolve()
    pasta_dados.mkdir(parents=True, exist_ok=True)
    _configurar_log(pasta_dados)

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    url_base = os.environ.get("SCHULZ_URL_BASE") or \
        f"http://{_ip_da_rede() if args.lan else '127.0.0.1'}:{args.porta}"
    operador = os.environ.get("SCHULZ_OPERADOR") or getpass.getuser() or "Usuário autenticado"

    servico = Servico(Configuracao(pasta_dados=pasta_dados, url_base=url_base.rstrip("/"), gerado_por=operador))
    app = criar_app(servico)
    logging.getLogger("schulz").info("Schulz local %s em %s (dados em %s)", VERSAO, url_base, pasta_dados)
    print(f"\n  Interface: http://127.0.0.1:{args.porta}/   (Ctrl+C para encerrar)\n", flush=True)
    app.run(host=host, port=args.porta, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
