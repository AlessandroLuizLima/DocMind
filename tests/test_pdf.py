"""Testes da leitura de PDF (docmind.pdf.ler_pdf) — geram PDFs mínimos na hora."""
from pypdf import PdfWriter

from docmind.pdf import ler_pdf


def _pdf_em_branco(caminho, paginas):
    escritor = PdfWriter()
    for _ in range(paginas):
        escritor.add_blank_page(width=200, height=200)
    with open(caminho, "wb") as f:
        escritor.write(f)


def test_ler_pdf_conta_paginas_numa_unica_leitura(tmp_path):
    caminho = tmp_path / "tres.pdf"
    _pdf_em_branco(caminho, 3)
    doc = ler_pdf(str(caminho))
    assert doc.paginas == 3


def test_pdf_sem_texto_volta_texto_vazio(tmp_path):
    caminho = tmp_path / "vazio.pdf"
    _pdf_em_branco(caminho, 1)
    assert ler_pdf(str(caminho)).texto == ""
