# ═══════════════════════════════════════════════════════════════
# DocMind — Interface Gráfica (Tkinter)
# Dark mode | Importar PDF | Resumo via IA | Perguntas e Respostas
# ═══════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import sys

# Adiciona o diretório pai ao path para importar os módulos do projeto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
import PyPDF2

# Importa funções do banco de dados
try:
    from database.database import inserir_documento, inserir_resumo, inserir_pergunta
    DB_DISPONIVEL = True
except Exception:
    DB_DISPONIVEL = False

# ── Configuração da API ──────────────────────────────────────
load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")

llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    anthropic_api_key=api_key,
    temperature=0.5
)

# ── Cores e fontes ───────────────────────────────────────────
COR_BG         = "#0f1117"   # fundo principal
COR_PAINEL     = "#1a1d27"   # painéis internos
COR_BORDA      = "#2a2d3e"   # bordas
COR_ACENTO     = "#7c6af7"   # roxo — cor de destaque
COR_ACENTO2    = "#4f9ef7"   # azul — secundário
COR_TEXTO      = "#e8e8f0"   # texto principal
COR_TEXTO2     = "#8b8fa8"   # texto secundário
COR_ENTRADA    = "#12151f"   # fundo dos campos de texto
COR_BTN        = "#7c6af7"   # fundo botão primário
COR_BTN_HOVER  = "#6a59e0"   # hover botão
COR_SUCESSO    = "#3dd68c"   # verde sucesso
COR_ERRO       = "#f76a6a"   # vermelho erro

FONTE_TITULO   = ("JetBrains Mono", 22, "bold")
FONTE_SUBTIT   = ("JetBrains Mono", 13)
FONTE_LABEL    = ("Inter", 10, "bold")
FONTE_TEXTO    = ("Inter", 11)
FONTE_BTN      = ("Inter", 10, "bold")
FONTE_PEQUENA  = ("Inter", 9)


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES DE IA
# ═══════════════════════════════════════════════════════════════

def extrair_texto_pdf(caminho):
    """Extrai texto de todas as páginas do PDF."""
    texto = ""
    with open(caminho, "rb") as f:
        leitor = PyPDF2.PdfReader(f)
        for pagina in leitor.pages:
            texto += pagina.extract_text() or ""
    return texto.strip()


def gerar_resumo(texto_pdf):
    """Envia o texto para a API do Claude e retorna o resumo."""
    prompt = ChatPromptTemplate.from_template(
        "Você é o DocMind, assistente especializado em documentos PDF.\n"
        "Responda sempre em português.\n\n"
        "Resuma o documento abaixo em tópicos claros e objetivos.\n"
        "Use no máximo 8 tópicos. Seja direto.\n\n"
        "Documento:\n{texto}"
    )
    chain = prompt | llm
    resposta = chain.invoke({"texto": texto_pdf[:12000]})
    return resposta.content


def responder_pergunta(texto_pdf, pergunta):
    """Responde uma pergunta com base no conteúdo do PDF."""
    prompt = ChatPromptTemplate.from_template(
        "Você é o DocMind, assistente especializado em análise de documentos PDF.\n"
        "Responda APENAS com base no texto abaixo. Se a informação não estiver no documento, diga claramente.\n"
        "Responda em português de forma objetiva.\n\n"
        "Documento:\n{texto}\n\n"
        "Pergunta: {pergunta}"
    )
    chain = prompt | llm
    resposta = chain.invoke({"texto": texto_pdf[:12000], "pergunta": pergunta})
    return resposta.content


# ═══════════════════════════════════════════════════════════════
# INTERFACE GRÁFICA
# ═══════════════════════════════════════════════════════════════

class DocMindApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DocMind")
        self.root.geometry("980x720")
        self.root.minsize(820, 600)
        self.root.configure(bg=COR_BG)

        self.texto_pdf    = ""
        self.nome_arquivo = ""
        self.documento_id = None

        self._construir_interface()

    # ── Layout principal ─────────────────────────────────────
    def _construir_interface(self):
        # Cabeçalho
        self._cabecalho()

        # Corpo principal: sidebar esquerda + área direita
        corpo = tk.Frame(self.root, bg=COR_BG)
        corpo.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._sidebar(corpo)
        self._area_principal(corpo)

        # Barra de status
        self._status_bar()

    def _cabecalho(self):
        frame = tk.Frame(self.root, bg=COR_PAINEL, height=64)
        frame.pack(fill="x")
        frame.pack_propagate(False)

        # Linha de acento no topo
        linha = tk.Frame(self.root, bg=COR_ACENTO, height=2)
        linha.pack(fill="x")

        tk.Label(
            frame, text="⬡ DocMind",
            font=FONTE_TITULO, fg=COR_TEXTO, bg=COR_PAINEL
        ).pack(side="left", padx=20, pady=12)

        tk.Label(
            frame, text="Assistente inteligente de documentos PDF",
            font=FONTE_SUBTIT, fg=COR_TEXTO2, bg=COR_PAINEL
        ).pack(side="left", padx=4, pady=12)

        # Indicador de API
        self.lbl_api = tk.Label(
            frame, text="● API desconectada",
            font=FONTE_PEQUENA, fg=COR_ERRO, bg=COR_PAINEL
        )
        self.lbl_api.pack(side="right", padx=20)
        self._verificar_api()

    def _sidebar(self, pai):
        self.sidebar = tk.Frame(pai, bg=COR_PAINEL, width=260, bd=0)
        self.sidebar.pack(side="left", fill="y", padx=(0, 12), pady=12)
        self.sidebar.pack_propagate(False)

        # Seção: Importar PDF
        self._secao_label(self.sidebar, "DOCUMENTO")

        self.lbl_arquivo = tk.Label(
            self.sidebar,
            text="Nenhum arquivo carregado",
            font=FONTE_PEQUENA, fg=COR_TEXTO2, bg=COR_PAINEL,
            wraplength=220, justify="left"
        )
        self.lbl_arquivo.pack(anchor="w", padx=16, pady=(0, 10))

        self._botao(
            self.sidebar, "Importar PDF",
            self._importar_pdf, icone="📂"
        ).pack(fill="x", padx=16, pady=(0, 6))

        self._botao(
            self.sidebar, "Gerar Resumo",
            self._gerar_resumo, icone="✦", cor=COR_ACENTO2
        ).pack(fill="x", padx=16, pady=(0, 16))

        # Separador
        tk.Frame(self.sidebar, bg=COR_BORDA, height=1).pack(fill="x", padx=16, pady=8)

        # Seção: informações do documento
        self._secao_label(self.sidebar, "INFORMAÇÕES")

        self.info_paginas = self._info_linha(self.sidebar, "Páginas", "—")
        self.info_chars   = self._info_linha(self.sidebar, "Caracteres", "—")
        self.info_db      = self._info_linha(
            self.sidebar, "Banco",
            "Conectado" if DB_DISPONIVEL else "Desconectado"
        )

        # Separador
        tk.Frame(self.sidebar, bg=COR_BORDA, height=1).pack(fill="x", padx=16, pady=8)

        # Seção: modo
        self._secao_label(self.sidebar, "MODO DA IA")
        self.modo_var = tk.StringVar(value="Detalhado")
        modos = ["Técnico", "Resumido", "Professor", "Detalhado", "Suporte"]
        for modo in modos:
            rb = tk.Radiobutton(
                self.sidebar, text=modo,
                variable=self.modo_var, value=modo,
                font=FONTE_PEQUENA, fg=COR_TEXTO, bg=COR_PAINEL,
                selectcolor=COR_ENTRADA, activebackground=COR_PAINEL,
                activeforeground=COR_ACENTO, cursor="hand2"
            )
            rb.pack(anchor="w", padx=20, pady=1)

    def _area_principal(self, pai):
        area = tk.Frame(pai, bg=COR_BG)
        area.pack(side="left", fill="both", expand=True, pady=12)

        # Abas: Resumo | Perguntas
        self.notebook = ttk.Notebook(area)
        self._estilizar_notebook()
        self.notebook.pack(fill="both", expand=True)

        self._aba_resumo()
        self._aba_perguntas()

    def _aba_resumo(self):
        aba = tk.Frame(self.notebook, bg=COR_PAINEL)
        self.notebook.add(aba, text="  Resumo  ")

        tk.Label(
            aba, text="Resumo gerado pela IA",
            font=FONTE_LABEL, fg=COR_ACENTO, bg=COR_PAINEL
        ).pack(anchor="w", padx=16, pady=(14, 6))

        frame_txt = tk.Frame(aba, bg=COR_BORDA, bd=1)
        frame_txt.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.txt_resumo = tk.Text(
            frame_txt,
            font=FONTE_TEXTO, fg=COR_TEXTO, bg=COR_ENTRADA,
            relief="flat", bd=0, padx=12, pady=12,
            wrap="word", cursor="arrow", state="disabled"
        )
        scroll_r = tk.Scrollbar(frame_txt, command=self.txt_resumo.yview, bg=COR_PAINEL)
        self.txt_resumo.configure(yscrollcommand=scroll_r.set)
        scroll_r.pack(side="right", fill="y")
        self.txt_resumo.pack(fill="both", expand=True)

        self._placeholder_texto(
            self.txt_resumo,
            "Importe um PDF e clique em 'Gerar Resumo' para ver o resumo aqui."
        )

    def _aba_perguntas(self):
        aba = tk.Frame(self.notebook, bg=COR_PAINEL)
        self.notebook.add(aba, text="  Perguntas  ")

        # Histórico de Q&A
        tk.Label(
            aba, text="Histórico de perguntas",
            font=FONTE_LABEL, fg=COR_ACENTO, bg=COR_PAINEL
        ).pack(anchor="w", padx=16, pady=(14, 6))

        frame_hist = tk.Frame(aba, bg=COR_BORDA, bd=1)
        frame_hist.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        self.txt_historico = tk.Text(
            frame_hist,
            font=FONTE_TEXTO, fg=COR_TEXTO, bg=COR_ENTRADA,
            relief="flat", bd=0, padx=12, pady=12,
            wrap="word", cursor="arrow", state="disabled"
        )
        scroll_h = tk.Scrollbar(frame_hist, command=self.txt_historico.yview, bg=COR_PAINEL)
        self.txt_historico.configure(yscrollcommand=scroll_h.set)
        scroll_h.pack(side="right", fill="y")
        self.txt_historico.pack(fill="both", expand=True)

        self._placeholder_texto(
            self.txt_historico,
            "As perguntas e respostas aparecerão aqui."
        )

        # Campo de pergunta
        tk.Label(
            aba, text="Sua pergunta",
            font=FONTE_LABEL, fg=COR_ACENTO, bg=COR_PAINEL
        ).pack(anchor="w", padx=16, pady=(0, 4))

        frame_entrada = tk.Frame(aba, bg=COR_PAINEL)
        frame_entrada.pack(fill="x", padx=16, pady=(0, 14))

        self.entrada_pergunta = tk.Entry(
            frame_entrada,
            font=FONTE_TEXTO, fg=COR_TEXTO, bg=COR_ENTRADA,
            relief="flat", bd=0, insertbackground=COR_ACENTO
        )
        self.entrada_pergunta.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.entrada_pergunta.bind("<Return>", lambda e: self._fazer_pergunta())

        self._botao(
            frame_entrada, "Perguntar",
            self._fazer_pergunta, icone="→"
        ).pack(side="right")

    # ── Ações ────────────────────────────────────────────────
    def _importar_pdf(self):
        caminho = filedialog.askopenfilename(
            title="Selecione um PDF",
            filetypes=[("Arquivos PDF", "*.pdf")]
        )
        if not caminho:
            return

        self._status("Lendo PDF...", COR_ACENTO2)
        try:
            self.texto_pdf    = extrair_texto_pdf(caminho)
            self.nome_arquivo = os.path.basename(caminho)

            # Contagem de páginas
            with open(caminho, "rb") as f:
                leitor = PyPDF2.PdfReader(f)
                num_paginas = len(leitor.pages)

            # Atualiza sidebar
            self.lbl_arquivo.config(text=self.nome_arquivo, fg=COR_TEXTO)
            self.info_paginas[1].config(text=str(num_paginas))
            self.info_chars[1].config(text=f"{len(self.texto_pdf):,}")

            # Salva no banco
            if DB_DISPONIVEL:
                self.documento_id = inserir_documento(
                    self.nome_arquivo, caminho, self.texto_pdf, num_paginas
                )

            self._placeholder_texto(
                self.txt_resumo,
                f"PDF '{self.nome_arquivo}' carregado com sucesso.\nClique em 'Gerar Resumo' para continuar."
            )
            self._limpar_historico()
            self._status(f"PDF carregado: {self.nome_arquivo}", COR_SUCESSO)

        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível ler o PDF:\n{e}")
            self._status("Erro ao ler PDF", COR_ERRO)

    def _gerar_resumo(self):
        if not self.texto_pdf:
            messagebox.showwarning("Atenção", "Importe um PDF primeiro.")
            return

        self._status("Gerando resumo...", COR_ACENTO)
        self._escrever_texto(self.txt_resumo, "⏳ Consultando a IA, aguarde...")

        def tarefa():
            try:
                resumo = gerar_resumo(self.texto_pdf)
                self.root.after(0, lambda: self._escrever_texto(self.txt_resumo, resumo))
                self.root.after(0, lambda: self._status("Resumo gerado!", COR_SUCESSO))

                if DB_DISPONIVEL and self.documento_id:
                    inserir_resumo(self.documento_id, resumo, 0, 0)

            except Exception as e:
                self.root.after(0, lambda: self._escrever_texto(
                    self.txt_resumo, f"Erro ao gerar resumo:\n{e}"
                ))
                self.root.after(0, lambda: self._status("Erro na API", COR_ERRO))

        threading.Thread(target=tarefa, daemon=True).start()

    def _fazer_pergunta(self):
        pergunta = self.entrada_pergunta.get().strip()
        if not pergunta:
            return
        if not self.texto_pdf:
            messagebox.showwarning("Atenção", "Importe um PDF antes de fazer perguntas.")
            return

        self.entrada_pergunta.delete(0, "end")
        self._status("Consultando a IA...", COR_ACENTO)
        self._acrescentar_historico(f"▶ {pergunta}\n", COR_ACENTO)
        self._acrescentar_historico("⏳ Aguarde...\n", COR_TEXTO2)
        self.notebook.select(1)

        def tarefa():
            try:
                resposta = responder_pergunta(self.texto_pdf, pergunta)
                self.root.after(0, lambda: self._substituir_ultima_linha(
                    f"◀ {resposta}\n{'─'*60}\n", COR_TEXTO
                ))
                self.root.after(0, lambda: self._status("Resposta recebida!", COR_SUCESSO))

                if DB_DISPONIVEL and self.documento_id:
                    inserir_pergunta(self.documento_id, pergunta, resposta, 0, 0)

            except Exception as e:
                self.root.after(0, lambda: self._substituir_ultima_linha(
                    f"Erro: {e}\n{'─'*60}\n", COR_ERRO
                ))
                self.root.after(0, lambda: self._status("Erro na API", COR_ERRO))

        threading.Thread(target=tarefa, daemon=True).start()

    # ── Helpers de UI ────────────────────────────────────────
    def _botao(self, pai, texto, comando, icone="", cor=None):
        cor = cor or COR_BTN
        btn = tk.Button(
            pai,
            text=f"{icone}  {texto}" if icone else texto,
            font=FONTE_BTN, fg="#ffffff", bg=cor,
            relief="flat", bd=0, padx=14, pady=8,
            cursor="hand2", command=comando,
            activebackground=COR_BTN_HOVER, activeforeground="#ffffff"
        )
        btn.bind("<Enter>", lambda e: btn.config(bg=COR_BTN_HOVER))
        btn.bind("<Leave>", lambda e: btn.config(bg=cor))
        return btn

    def _secao_label(self, pai, texto):
        tk.Label(
            pai, text=texto,
            font=FONTE_LABEL, fg=COR_ACENTO, bg=COR_PAINEL
        ).pack(anchor="w", padx=16, pady=(14, 6))

    def _info_linha(self, pai, chave, valor):
        frame = tk.Frame(pai, bg=COR_PAINEL)
        frame.pack(fill="x", padx=16, pady=2)
        lbl_chave = tk.Label(frame, text=chave, font=FONTE_PEQUENA, fg=COR_TEXTO2, bg=COR_PAINEL)
        lbl_chave.pack(side="left")
        lbl_valor = tk.Label(frame, text=valor, font=FONTE_PEQUENA, fg=COR_TEXTO, bg=COR_PAINEL)
        lbl_valor.pack(side="right")
        return lbl_chave, lbl_valor

    def _status_bar(self):
        bar = tk.Frame(self.root, bg=COR_PAINEL, height=28)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Frame(self.root, bg=COR_BORDA, height=1).pack(fill="x", side="bottom")
        self.lbl_status = tk.Label(
            bar, text="Pronto.",
            font=FONTE_PEQUENA, fg=COR_TEXTO2, bg=COR_PAINEL
        )
        self.lbl_status.pack(side="left", padx=16)

    def _status(self, msg, cor=None):
        self.lbl_status.config(text=msg, fg=cor or COR_TEXTO2)

    def _estilizar_notebook(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "TNotebook", background=COR_BG, borderwidth=0
        )
        style.configure(
            "TNotebook.Tab",
            background=COR_PAINEL, foreground=COR_TEXTO2,
            padding=[16, 8], font=FONTE_LABEL, borderwidth=0
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COR_PAINEL)],
            foreground=[("selected", COR_ACENTO)],
        )

    def _placeholder_texto(self, widget, texto):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", texto)
        widget.config(state="disabled", fg=COR_TEXTO2)

    def _escrever_texto(self, widget, texto):
        widget.config(state="normal", fg=COR_TEXTO)
        widget.delete("1.0", "end")
        widget.insert("end", texto)
        widget.config(state="disabled")

    def _acrescentar_historico(self, texto, cor):
        self.txt_historico.config(state="normal", fg=COR_TEXTO)
        self.txt_historico.insert("end", texto)
        self.txt_historico.see("end")
        self.txt_historico.config(state="disabled")

    def _substituir_ultima_linha(self, texto, cor):
        self.txt_historico.config(state="normal")
        self.txt_historico.delete("end-2l", "end-1c")
        self.txt_historico.insert("end", texto)
        self.txt_historico.see("end")
        self.txt_historico.config(state="disabled")

    def _limpar_historico(self):
        self.txt_historico.config(state="normal")
        self.txt_historico.delete("1.0", "end")
        self.txt_historico.config(state="disabled")

    def _verificar_api(self):
        if api_key and api_key != "sua-chave-aqui":
            self.lbl_api.config(text="● API conectada", fg=COR_SUCESSO)
        else:
            self.lbl_api.config(text="● API desconectada", fg=COR_ERRO)


# ═══════════════════════════════════════════════════════════════
# INICIALIZAÇÃO
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    root = tk.Tk()
    app = DocMindApp(root)
    root.mainloop()