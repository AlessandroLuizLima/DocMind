"""Leitura de PDFs (do disco ou por link)."""

import os
import re
import uuid
from collections import namedtuple
from urllib.parse import unquote, urlparse

import requests
from pypdf import PdfReader

RAIZ_PROJETO    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_DOWNLOADS = os.path.join(RAIZ_PROJETO, "pdfs_baixados")
TAMANHO_MAX_PDF = 40 * 1024 * 1024  # 40 MB

DocumentoPDF = namedtuple("DocumentoPDF", ["texto", "paginas"])


def ler_pdf(caminho):
    """Lê o PDF uma única vez e devolve o texto extraído e o número de páginas."""
    with open(caminho, "rb") as f:
        leitor = PdfReader(f)
        texto = "\n".join((pagina.extract_text() or "") for pagina in leitor.pages)
        return DocumentoPDF(texto.strip(), len(leitor.pages))


def _nome_arquivo_da_url(url, content_disposition):
    """Descobre um nome de arquivo razoável a partir do cabeçalho ou da própria URL."""
    if content_disposition:
        m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', content_disposition, re.IGNORECASE)
        if m:
            nome = os.path.basename(unquote(m.group(1).strip().strip('"')))
            if nome:
                return nome if nome.lower().endswith(".pdf") else nome + ".pdf"

    nome = os.path.basename(unquote(urlparse(url).path)) or "documento"
    return nome if nome.lower().endswith(".pdf") else nome + ".pdf"


def baixar_pdf(url, pasta_destino=None):
    """Baixa um PDF de uma URL http(s), valida o conteúdo e salva localmente.
    Levanta ValueError com uma mensagem amigável em caso de problema.
    Retorna (caminho_local, nome_arquivo)."""
    pasta_destino = pasta_destino or PASTA_DOWNLOADS
    os.makedirs(pasta_destino, exist_ok=True)

    try:
        resposta = requests.get(
            url, timeout=25, stream=True,
            headers={"User-Agent": "Mozilla/5.0 (DocMind)"}
        )
        resposta.raise_for_status()
    except requests.exceptions.Timeout:
        raise ValueError("O link demorou demais para responder (timeout).")
    except requests.exceptions.SSLError:
        raise ValueError("Não foi possível validar o certificado de segurança do site.")
    except requests.exceptions.ConnectionError:
        raise ValueError("Não foi possível conectar ao link informado.")
    except requests.exceptions.HTTPError:
        raise ValueError(f"O link respondeu com erro {resposta.status_code}.")

    tamanho_previsto = int(resposta.headers.get("Content-Length") or 0)
    if tamanho_previsto > TAMANHO_MAX_PDF:
        raise ValueError(
            f"O arquivo tem {tamanho_previsto / 1_000_000:.1f} MB; "
            f"o limite é {TAMANHO_MAX_PDF // 1_000_000} MB."
        )

    nome_arquivo = _nome_arquivo_da_url(url, resposta.headers.get("Content-Disposition"))
    destino = os.path.join(pasta_destino, f"{uuid.uuid4().hex[:8]}_{nome_arquivo}")

    escrito = 0
    try:
        with open(destino, "wb") as f:
            for pedaco in resposta.iter_content(chunk_size=65536):
                escrito += len(pedaco)
                if escrito > TAMANHO_MAX_PDF:
                    raise ValueError(f"O arquivo excede o limite de {TAMANHO_MAX_PDF // 1_000_000} MB.")
                f.write(pedaco)

        with open(destino, "rb") as f:
            if f.read(5) != b"%PDF-":
                raise ValueError("O link não aponta para um arquivo PDF válido.")
    except Exception:
        if os.path.exists(destino):
            os.remove(destino)
        raise

    return destino, nome_arquivo
