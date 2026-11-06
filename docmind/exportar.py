"""Exportação de resumos e conversas em Markdown (.md).

Markdown abre em qualquer editor, fica bonito no GitHub/Notion/Obsidian
e pode ser colado direto num relatório ou trabalho.
"""

import os
import re
from datetime import datetime


def _agora():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _papel_e_conteudo(mensagem):
    """Aceita tuplas (papel, conteudo) ou dicionários vindos do banco."""
    if isinstance(mensagem, dict):
        return mensagem.get("papel"), mensagem.get("conteudo") or ""
    papel, conteudo = mensagem[0], mensagem[1]
    return papel, conteudo or ""


def resumo_para_markdown(nome_arquivo, resumo, modo=None, data=None):
    """Monta um arquivo Markdown com o resumo de um documento."""
    meta = [f"**Documento:** {nome_arquivo}"]
    if modo:
        meta.append(f"**Modo da IA:** {modo}")
    meta.append(f"**Gerado em:** {data or _agora()}")
    return (
        f"# Resumo — {nome_arquivo}\n\n"
        + "  \n".join(meta)
        + "\n\n---\n\n"
        + resumo.strip()
        + "\n\n---\n*Gerado pelo DocMind.*\n"
    )


def conversa_para_markdown(nome_arquivo, mensagens, modo=None, titulo=None, data=None):
    """Monta um arquivo Markdown com as perguntas e respostas de uma conversa."""
    meta = [f"**Documento:** {nome_arquivo}"]
    if modo:
        meta.append(f"**Modo da IA:** {modo}")
    meta.append(f"**Exportado em:** {data or _agora()}")

    blocos = []
    for mensagem in mensagens:
        papel, conteudo = _papel_e_conteudo(mensagem)
        if papel == "usuario":
            blocos.append(f"### Pergunta\n\n{conteudo.strip()}")
        else:
            blocos.append(f"**DocMind:**\n\n{conteudo.strip()}")

    return (
        f"# {titulo or 'Conversa'} — {nome_arquivo}\n\n"
        + "  \n".join(meta)
        + "\n\n---\n\n"
        + "\n\n".join(blocos)
        + "\n\n---\n*Gerado pelo DocMind.*\n"
    )


def nome_sugerido(nome_arquivo, sufixo):
    """'Contrato Final.pdf' + 'resumo' → 'Contrato Final - resumo.md'
    (sem caracteres que o Windows não aceita em nomes de arquivo)."""
    base = os.path.splitext(os.path.basename(nome_arquivo or "documento"))[0]
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base).strip(" .") or "documento"
    return f"{base} - {sufixo}.md"
