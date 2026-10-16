"""Testes do download de PDF por link — usam um servidor HTTP local, sem internet."""
import http.server
import os
import threading
import time

import pytest

import app as A

CONTEUDO_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF"
)


class Servidor(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/documento.pdf":
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(CONTEUDO_PDF)))
            self.end_headers()
            self.wfile.write(CONTEUDO_PDF)
        elif self.path == "/com-nome.pdf":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="Relatorio Final.pdf"')
            self.end_headers()
            self.wfile.write(CONTEUDO_PDF)
        elif self.path == "/pagina.html":
            corpo = b"<html><body>nao sou um pdf</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(corpo)
        elif self.path == "/grande.pdf":
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.end_headers()
            self.wfile.write(CONTEUDO_PDF + b"0" * 2000)
        elif self.path == "/nao-existe.pdf":
            self.send_response(404)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # silencia o log do servidor de teste


@pytest.fixture(scope="module")
def servidor():
    httpd = http.server.HTTPServer(("127.0.0.1", 0), Servidor)
    porta = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)
    yield f"http://127.0.0.1:{porta}"
    httpd.shutdown()


@pytest.fixture
def pasta(tmp_path):
    return str(tmp_path)


def test_baixa_pdf_valido_e_confirma_pelos_bytes(servidor, pasta):
    caminho, nome = A.baixar_pdf(f"{servidor}/documento.pdf", pasta)
    assert nome == "documento.pdf"
    assert os.path.exists(caminho)
    with open(caminho, "rb") as f:
        assert f.read().startswith(b"%PDF-")


def test_usa_nome_do_content_disposition(servidor, pasta):
    caminho, nome = A.baixar_pdf(f"{servidor}/com-nome.pdf", pasta)
    assert nome == "Relatorio Final.pdf"
    assert os.path.exists(caminho)


def test_rejeita_conteudo_que_nao_e_pdf(servidor, pasta):
    with pytest.raises(ValueError, match="não aponta para um arquivo PDF válido"):
        A.baixar_pdf(f"{servidor}/pagina.html", pasta)
    assert os.listdir(pasta) == []  # não deixa lixo para trás


def test_respeita_limite_de_tamanho_durante_o_download(servidor, pasta, monkeypatch):
    monkeypatch.setattr(A, "TAMANHO_MAX_PDF", 100)  # bem menor que /grande.pdf
    with pytest.raises(ValueError, match="excede o limite"):
        A.baixar_pdf(f"{servidor}/grande.pdf", pasta)
    assert os.listdir(pasta) == []


def test_erro_404_gera_mensagem_amigavel(servidor, pasta):
    with pytest.raises(ValueError, match="erro 404"):
        A.baixar_pdf(f"{servidor}/nao-existe.pdf", pasta)


def test_conexao_recusada_gera_mensagem_amigavel(pasta):
    with pytest.raises(ValueError, match="conectar"):
        A.baixar_pdf("http://127.0.0.1:1/inexistente.pdf", pasta)


def test_nomes_repetidos_nao_se_sobrescrevem(servidor, pasta):
    c1, _ = A.baixar_pdf(f"{servidor}/documento.pdf", pasta)
    c2, _ = A.baixar_pdf(f"{servidor}/documento.pdf", pasta)
    assert c1 != c2
    assert os.path.exists(c1) and os.path.exists(c2)
