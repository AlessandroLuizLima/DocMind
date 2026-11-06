"""Testes da exportação em Markdown."""
from docmind.exportar import conversa_para_markdown, nome_sugerido, resumo_para_markdown


def test_resumo_traz_documento_modo_data_e_conteudo():
    md = resumo_para_markdown("contrato.pdf", "- Valor: R$ 15.000,00\n", "Resumido", data="01/01/2026 10:00")
    assert md.startswith("# Resumo — contrato.pdf")
    assert "**Modo da IA:** Resumido" in md
    assert "01/01/2026 10:00" in md
    assert "- Valor: R$ 15.000,00" in md


def test_conversa_aceita_tuplas_e_dicionarios_do_banco():
    tuplas = [("usuario", "Qual o prazo?"), ("ia", "90 dias.")]
    dicts = [{"papel": "usuario", "conteudo": "Qual o prazo?"}, {"papel": "ia", "conteudo": "90 dias."}]
    md1 = conversa_para_markdown("c.pdf", tuplas, data="x")
    md2 = conversa_para_markdown("c.pdf", dicts, data="x")
    assert md1 == md2
    assert md1.index("### Pergunta") < md1.index("Qual o prazo?") < md1.index("**DocMind:**") < md1.index("90 dias.")


def test_conversa_sem_modo_nao_mostra_linha_de_modo():
    assert "Modo da IA" not in conversa_para_markdown("c.pdf", [], data="x")


def test_nome_sugerido_remove_extensao_e_caracteres_invalidos():
    assert nome_sugerido("Contrato Final.pdf", "resumo") == "Contrato Final - resumo.md"
    assert nome_sugerido('a:b*c?.pdf', "conversa") == "a_b_c_ - conversa.md"
    assert nome_sugerido("", "resumo") == "documento - resumo.md"
