"""Pacote compartilhado do DocMind.

Reúne a lógica que não depende da interface gráfica, para poder ser
reutilizada e testada sem abrir janela nenhuma:

- docmind.pdf        → leitura de PDFs e download por link
- docmind.seguranca  → validação das perguntas (prompt injection etc.)
- docmind.exportar   → exportação de resumos e conversas em Markdown
"""

__version__ = "1.1.0"
