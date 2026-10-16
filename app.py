import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import threading
import os
import sys
import re
import ctypes
import uuid
from urllib.parse import urlparse, unquote

# ── Corrige o borrão em telas com escala do Windows (DPI) ────
# Precisa rodar ANTES de criar a janela Tk().
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# Adiciona o diretório pai ao path para importar os módulos do projeto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
import PyPDF2
import requests
from datetime import datetime

# Importa a lógica de IA (modos, resumo, perguntas, segurança e roteamento)
from DocMindAPI import (
    MODOS, ANTHROPIC_API_KEY, nomes_dos_modos, gerar_resumo, responder_pergunta
)

# Importa funções do banco de dados (cria as tabelas na primeira execução)
try:
    from database import database as db
    db.criar_tabelas()
    DB_DISPONIVEL = True
except Exception:
    db = None
    DB_DISPONIVEL = False

load_dotenv()

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

# ── Download de PDF por link ──────────────────────────────────
PASTA_DOWNLOADS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdfs_baixados")
os.makedirs(PASTA_DOWNLOADS, exist_ok=True)
TAMANHO_MAX_PDF = 40 * 1024 * 1024  # 40 MB


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════

def extrair_texto_pdf(caminho):
    """Extrai texto de todas as páginas do PDF."""
    texto = ""
    with open(caminho, "rb") as f:
        leitor = PyPDF2.PdfReader(f)
        for pagina in leitor.pages:
            texto += pagina.extract_text() or ""
    return texto.strip()


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


def baixar_pdf(url, pasta_destino=PASTA_DOWNLOADS):
    """Baixa um PDF de uma URL http(s), valida o conteúdo e salva localmente.
    Levanta ValueError com uma mensagem amigável em caso de problema.
    Retorna (caminho_local, nome_arquivo)."""
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


# ═══════════════════════════════════════════════════════════════
# INTERFACE GRÁFICA
# ═══════════════════════════════════════════════════════════════

class DocMindApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DocMind")
        self.root.geometry("1040x800")
        self.root.minsize(900, 700)
        self.root.configure(bg=COR_BG)

        self.texto_pdf    = ""
        self.nome_arquivo = ""
        self.documento_id = None
        self.conversa_id  = None     # conversa atual na aba Perguntas
        self.mensagens    = []       # [(papel, conteudo)] da conversa atual
        self._lock_db     = threading.Lock()
        self._ids_historico = []     # ids das linhas exibidas na aba Histórico

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

        tk.Label(
            self.sidebar, text="ou cole o link de um PDF",
            font=FONTE_PEQUENA, fg=COR_TEXTO2, bg=COR_PAINEL
        ).pack(anchor="w", padx=16, pady=(2, 4))

        frame_url = tk.Frame(self.sidebar, bg=COR_PAINEL)
        frame_url.pack(fill="x", padx=16, pady=(0, 6))

        self.entrada_url = tk.Entry(
            frame_url, width=1,  # largura mínima: o fill="x" + expand quem define o tamanho real
            font=FONTE_PEQUENA, fg=COR_TEXTO, bg=COR_ENTRADA,
            relief="flat", bd=0, insertbackground=COR_ACENTO
        )
        self.entrada_url.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
        self.entrada_url.bind("<Return>", lambda e: self._importar_pdf_por_link())

        btn_baixar = self._botao(frame_url, "Baixar", self._importar_pdf_por_link)
        # width em caracteres: garante um tamanho mínimo fixo, independente da fonte
        # disponível no sistema (a "Inter" pode não existir no Windows e cair numa
        # fonte substituta mais larga, que antes cortava o texto do botão).
        btn_baixar.config(padx=10, width=7)
        btn_baixar.pack(side="right")

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
        for modo in nomes_dos_modos():
            rb = tk.Radiobutton(
                self.sidebar, text=modo,
                variable=self.modo_var, value=modo,
                command=self._atualizar_descricao_modo,
                font=FONTE_PEQUENA, fg=COR_TEXTO, bg=COR_PAINEL,
                selectcolor=COR_ENTRADA, activebackground=COR_PAINEL,
                activeforeground=COR_ACENTO, cursor="hand2"
            )
            rb.pack(anchor="w", padx=20, pady=1)

        self.lbl_modo_desc = tk.Label(
            self.sidebar, text="", font=("Inter", 8), fg=COR_TEXTO2, bg=COR_PAINEL,
            wraplength=220, justify="left"
        )
        self.lbl_modo_desc.pack(anchor="w", padx=20, pady=(6, 4))
        self._atualizar_descricao_modo()

        self.exemplo_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            self.sidebar, text="Exemplo prático nas respostas",
            variable=self.exemplo_var,
            font=FONTE_PEQUENA, fg=COR_TEXTO, bg=COR_PAINEL,
            selectcolor=COR_ACENTO, activebackground=COR_PAINEL,
            activeforeground=COR_ACENTO, cursor="hand2",
            wraplength=210, justify="left", anchor="w"
        ).pack(anchor="w", fill="x", padx=18, pady=(6, 2))

        tk.Label(
            self.sidebar,
            text="Adiciona um caso prático ao final de cada resposta.",
            font=("Inter", 8), fg=COR_TEXTO2, bg=COR_PAINEL,
            wraplength=210, justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 8))

    def _area_principal(self, pai):
        area = tk.Frame(pai, bg=COR_BG)
        area.pack(side="left", fill="both", expand=True, pady=12)

        # Abas: Resumo | Perguntas | Histórico
        self.notebook = ttk.Notebook(area)
        self._estilizar_notebook()
        self.notebook.pack(fill="both", expand=True)

        self._aba_resumo()
        self._aba_perguntas()
        self._aba_historico()
        self.notebook.bind("<<NotebookTabChanged>>", self._ao_trocar_aba)

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
            relief="flat", bd=0, padx=14, pady=14,
            wrap="word", cursor="arrow", state="disabled"
        )
        scroll_r = tk.Scrollbar(frame_txt, command=self.txt_resumo.yview, bg=COR_PAINEL)
        self.txt_resumo.configure(yscrollcommand=scroll_r.set)
        scroll_r.pack(side="right", fill="y")
        self.txt_resumo.pack(fill="both", expand=True)

        self._configurar_tags_texto(self.txt_resumo, "resumo")

        self._placeholder_texto(
            self.txt_resumo,
            "Importe um PDF e clique em 'Gerar Resumo' para ver o resumo aqui."
        )

    def _aba_perguntas(self):
        aba = tk.Frame(self.notebook, bg=COR_PAINEL)
        self.notebook.add(aba, text="  Perguntas  ")

        # Conversa atual
        topo = tk.Frame(aba, bg=COR_PAINEL)
        topo.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(
            topo, text="Conversa",
            font=FONTE_LABEL, fg=COR_ACENTO, bg=COR_PAINEL
        ).pack(side="left")
        self._botao(
            topo, "Nova conversa", self._nova_conversa, icone="+", cor=COR_ACENTO2
        ).pack(side="right")

        frame_hist = tk.Frame(aba, bg=COR_BORDA, bd=1)
        frame_hist.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        self.txt_historico = tk.Text(
            frame_hist,
            font=FONTE_TEXTO, fg=COR_TEXTO, bg=COR_ENTRADA,
            relief="flat", bd=0, padx=14, pady=14,
            wrap="word", cursor="arrow", state="disabled"
        )
        scroll_h = tk.Scrollbar(frame_hist, command=self.txt_historico.yview, bg=COR_PAINEL)
        self.txt_historico.configure(yscrollcommand=scroll_h.set)
        scroll_h.pack(side="right", fill="y")
        self.txt_historico.pack(fill="both", expand=True)

        self._configurar_tags_chat(self.txt_historico)

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
    def _atualizar_descricao_modo(self):
        modo = next((m for m in MODOS.values() if m["nome"] == self.modo_var.get()), None)
        self.lbl_modo_desc.config(text=modo["descricao"] if modo else "")

    def _importar_pdf(self):
        caminho = filedialog.askopenfilename(
            title="Selecione um PDF",
            filetypes=[("Arquivos PDF", "*.pdf")]
        )
        if not caminho:
            return

        self._status("Lendo PDF...", COR_ACENTO2)
        try:
            self._finalizar_importacao(caminho, os.path.basename(caminho))
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível ler o PDF:\n{e}")
            self._status("Erro ao ler PDF", COR_ERRO)

    def _importar_pdf_por_link(self):
        url = self.entrada_url.get().strip()
        if not url:
            return
        if not re.match(r"^https?://", url, re.IGNORECASE):
            messagebox.showwarning("Atenção", "Cole um link http:// ou https:// válido.")
            self.entrada_url.delete(0, "end")
            return

        self.entrada_url.delete(0, "end")
        self._status("Baixando PDF do link...", COR_ACENTO2)

        def tarefa():
            try:
                caminho, nome_arquivo = baixar_pdf(url)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Erro", f"Não foi possível baixar o PDF:\n{e}"
                ))
                self.root.after(0, lambda: self._status("Erro ao baixar PDF", COR_ERRO))
                return

            def concluir():
                try:
                    self._finalizar_importacao(caminho, nome_arquivo)
                except Exception as e:
                    messagebox.showerror("Erro", f"Não foi possível ler o PDF baixado:\n{e}")
                    self._status("Erro ao ler PDF", COR_ERRO)

            self.root.after(0, concluir)

        threading.Thread(target=tarefa, daemon=True).start()

    def _finalizar_importacao(self, caminho, nome_arquivo):
        """Passo comum entre importar do disco e baixar por link:
        extrai o texto, atualiza a sidebar e salva o documento no banco."""
        self.texto_pdf    = extrair_texto_pdf(caminho)
        self.nome_arquivo = nome_arquivo

        with open(caminho, "rb") as f:
            leitor = PyPDF2.PdfReader(f)
            num_paginas = len(leitor.pages)

        self.lbl_arquivo.config(text=self.nome_arquivo, fg=COR_TEXTO)
        self.info_paginas[1].config(text=str(num_paginas))
        self.info_chars[1].config(text=f"{len(self.texto_pdf):,}")

        self.documento_id = None
        if DB_DISPONIVEL:
            self.documento_id = db.inserir_documento(
                self.nome_arquivo, caminho, self.texto_pdf, num_paginas
            )

        self._placeholder_texto(
            self.txt_resumo,
            f"PDF '{self.nome_arquivo}' carregado com sucesso.\nClique em 'Gerar Resumo' para continuar."
        )
        self._nova_conversa()
        self._status(f"PDF carregado: {self.nome_arquivo}", COR_SUCESSO)

    def _gerar_resumo(self):
        if not self.texto_pdf:
            messagebox.showwarning("Atenção", "Importe um PDF primeiro.")
            return

        modo_nome = self.modo_var.get()
        documento_id = self.documento_id
        self._status(f"Gerando resumo (modo {modo_nome})...", COR_ACENTO)
        self._placeholder_texto(self.txt_resumo, "Consultando a IA, aguarde...")

        def progresso(i, total):
            self.root.after(0, lambda: self._status(
                f"Resumindo parte {i} de {total} (modo {modo_nome})...", COR_ACENTO
            ))

        def tarefa():
            try:
                res = gerar_resumo(self.texto_pdf, modo_nome, progresso=progresso)
            except Exception as e:
                self.root.after(0, lambda: self._escrever_texto(
                    self.txt_resumo, f"Erro ao gerar resumo:\n{e}", erro=True
                ))
                self.root.after(0, lambda: self._status("Erro na API", COR_ERRO))
                return

            self.root.after(0, lambda: self._escrever_texto(self.txt_resumo, res.texto))
            self.root.after(0, lambda: self._status("Resumo gerado!", COR_SUCESSO))
            self._salvar_resumo(documento_id, res, modo_nome)

        threading.Thread(target=tarefa, daemon=True).start()

    def _fazer_pergunta(self):
        pergunta = self.entrada_pergunta.get().strip()
        if not pergunta:
            return
        if not self.texto_pdf:
            messagebox.showwarning("Atenção", "Importe um PDF antes de fazer perguntas.")
            return

        modo_nome       = self.modo_var.get()
        incluir_exemplo = self.exemplo_var.get()
        documento_id    = self.documento_id
        historico       = list(self.mensagens)   # contexto: mensagens anteriores da conversa
        self.entrada_pergunta.delete(0, "end")
        self._status("Consultando a IA...", COR_ACENTO)
        self._iniciar_pergunta_no_historico(pergunta)
        self.notebook.select(1)

        def tarefa():
            try:
                res = responder_pergunta(
                    self.texto_pdf, pergunta, modo_nome,
                    historico=historico, incluir_exemplo=incluir_exemplo
                )
            except Exception as e:
                self.root.after(0, lambda: self._concluir_resposta_no_historico(str(e), erro=True))
                self.root.after(0, lambda: self._status("Erro na API", COR_ERRO))
                return

            meta = res.api if res.bloqueado else f"{res.api} • modo {modo_nome}"
            self.root.after(0, lambda: self._concluir_resposta_no_historico(res.texto, meta))
            self.root.after(0, lambda: self._status("Resposta recebida!", COR_SUCESSO))

            if not res.bloqueado:
                self.mensagens += [("usuario", pergunta), ("ia", res.texto)]
                self._salvar_pergunta(documento_id, pergunta, res, modo_nome)

        threading.Thread(target=tarefa, daemon=True).start()

    # ── Persistência (o app continua funcionando se o banco cair) ──
    def _aviso_banco(self, erro):
        self.root.after(0, lambda: self._status(
            f"Aviso: não foi possível salvar no histórico ({erro})", COR_ERRO
        ))

    def _salvar_resumo(self, documento_id, res, modo_nome):
        if not (DB_DISPONIVEL and documento_id):
            return
        try:
            db.inserir_resumo(documento_id, res.texto, res.tokens_entrada, res.tokens_saida)
            conversa = db.criar_conversa(
                documento_id, f"Resumo — {self.nome_arquivo}", "resumo", modo_nome
            )
            db.inserir_mensagem(conversa, "ia", res.texto, modo_nome, res.api)
        except Exception as e:
            self._aviso_banco(e)

    def _salvar_pergunta(self, documento_id, pergunta, res, modo_nome):
        if not (DB_DISPONIVEL and documento_id):
            return
        try:
            with self._lock_db:
                if self.conversa_id is None:
                    titulo = pergunta if len(pergunta) <= 60 else pergunta[:57] + "..."
                    self.conversa_id = db.criar_conversa(documento_id, titulo, "perguntas", modo_nome)
                conversa = self.conversa_id
            db.inserir_pergunta(documento_id, pergunta, res.texto, res.tokens_entrada, res.tokens_saida)
            db.inserir_mensagem(conversa, "usuario", pergunta, modo_nome)
            db.inserir_mensagem(conversa, "ia", res.texto, modo_nome, res.api)
        except Exception as e:
            self._aviso_banco(e)

    def _nova_conversa(self):
        """Começa uma conversa nova (o documento continua carregado)."""
        self.conversa_id = None
        self.mensagens = []
        self._limpar_historico()

    # ── Aba Histórico ────────────────────────────────────────
    def _aba_historico(self):
        aba = tk.Frame(self.notebook, bg=COR_PAINEL)
        self.notebook.add(aba, text="  Histórico  ")

        # Barra de busca e filtro
        barra = tk.Frame(aba, bg=COR_PAINEL)
        barra.pack(fill="x", padx=16, pady=(14, 8))

        self.busca_var = tk.StringVar()
        entrada = tk.Entry(
            barra, textvariable=self.busca_var, font=FONTE_TEXTO,
            fg=COR_TEXTO, bg=COR_ENTRADA, relief="flat", bd=0, insertbackground=COR_ACENTO
        )
        entrada.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        entrada.bind("<Return>", lambda e: self._atualizar_historico())
        self._busca_job = None
        self.busca_var.trace_add("write", lambda *a: self._agendar_busca())

        tk.Label(
            barra, text="Mostrar:",
            font=FONTE_PEQUENA, fg=COR_TEXTO2, bg=COR_PAINEL
        ).pack(side="left", padx=(0, 6))

        self.filtro_var = tk.StringVar(value="Todos")
        filtro = ttk.Combobox(
            barra, textvariable=self.filtro_var, state="readonly", width=13,
            values=["Todos", "Conversas", "Resumos"]
        )
        filtro.pack(side="left", padx=(0, 8))
        filtro.bind("<<ComboboxSelected>>", lambda e: self._atualizar_historico())

        self._botao(barra, "Atualizar", self._atualizar_historico, icone="↻").pack(side="left")

        # Lista + visualização
        corpo = tk.Frame(aba, bg=COR_PAINEL)
        corpo.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        esq = tk.Frame(corpo, bg=COR_BORDA, bd=1, width=360)
        esq.pack(side="left", fill="y", padx=(0, 10))
        esq.pack_propagate(False)

        estilo = ttk.Style()
        estilo.configure(
            "Historico.Treeview", background=COR_ENTRADA, foreground=COR_TEXTO,
            fieldbackground=COR_ENTRADA, borderwidth=0, rowheight=44, font=FONTE_PEQUENA
        )
        estilo.map("Historico.Treeview", background=[("selected", COR_ACENTO)])

        self.lista_hist = ttk.Treeview(
            esq, style="Historico.Treeview", show="tree", selectmode="browse"
        )
        scroll_l = tk.Scrollbar(esq, command=self.lista_hist.yview, bg=COR_PAINEL)
        self.lista_hist.configure(yscrollcommand=scroll_l.set)
        scroll_l.pack(side="right", fill="y")
        self.lista_hist.pack(fill="both", expand=True)
        self.lista_hist.bind("<<TreeviewSelect>>", lambda e: self._mostrar_conversa_selecionada())
        self.lista_hist.bind("<Double-1>", lambda e: self._abrir_conversa_selecionada())

        dir_ = tk.Frame(corpo, bg=COR_BORDA, bd=1)
        dir_.pack(side="left", fill="both", expand=True)
        self.txt_visualizacao = tk.Text(
            dir_, font=FONTE_TEXTO, fg=COR_TEXTO, bg=COR_ENTRADA,
            relief="flat", bd=0, padx=14, pady=14, wrap="word",
            cursor="arrow", state="disabled"
        )
        scroll_v = tk.Scrollbar(dir_, command=self.txt_visualizacao.yview, bg=COR_PAINEL)
        self.txt_visualizacao.configure(yscrollcommand=scroll_v.set)
        scroll_v.pack(side="right", fill="y")
        self.txt_visualizacao.pack(fill="both", expand=True)
        self._configurar_tags_chat(self.txt_visualizacao)

        # Ações (desabilitadas até o usuário selecionar algo na lista)
        acoes = tk.Frame(aba, bg=COR_PAINEL)
        acoes.pack(fill="x", padx=16, pady=(0, 14))
        self.btn_abrir = self._botao(acoes, "Continuar conversa", self._abrir_conversa_selecionada, icone="→")
        self.btn_abrir.pack(side="left")
        self.btn_renomear = self._botao(acoes, "Renomear", self._renomear_conversa_selecionada, cor=COR_ACENTO2)
        self.btn_renomear.pack(side="left", padx=8)
        self.btn_excluir = self._botao(acoes, "Excluir", self._excluir_conversa_selecionada, cor=COR_ERRO)
        self.btn_excluir.pack(side="left")
        self._estado_botoes_historico(selecionado=False)

        self._mensagem_visualizacao(
            "Selecione uma conversa ou resumo na lista para visualizar." if DB_DISPONIVEL
            else "Banco de dados indisponível: o histórico não pode ser carregado."
        )

    def _ao_trocar_aba(self, _evento=None):
        if self.notebook.index(self.notebook.select()) == 2:
            self._atualizar_historico()

    def _agendar_busca(self):
        """Espera o usuário parar de digitar antes de consultar o banco."""
        if self._busca_job:
            self.root.after_cancel(self._busca_job)
        self._busca_job = self.root.after(350, self._atualizar_historico)

    def _atualizar_historico(self):
        self.lista_hist.delete(*self.lista_hist.get_children())
        self._ids_historico = []
        if not DB_DISPONIVEL:
            return
        tipo = {"Conversas": "perguntas", "Resumos": "resumo"}.get(self.filtro_var.get())
        self._estado_botoes_historico(selecionado=False)
        try:
            conversas = db.listar_conversas(self.busca_var.get(), tipo)
        except Exception as e:
            self._mensagem_visualizacao(f"Erro ao carregar o histórico:\n{e}")
            return

        for c in conversas:
            icone = "✦" if c["tipo"] == "resumo" else "💬"
            data = c["data_atualizacao"].strftime("%d/%m %H:%M")
            arquivo = c["nome_arquivo"] if len(c["nome_arquivo"]) <= 18 else c["nome_arquivo"][:15] + "..."
            modo = f" • {c['modo']}" if c["modo"] else ""
            texto = f"{icone} {c['titulo']}\n     {arquivo}{modo} • {data}"
            self.lista_hist.insert("", "end", iid=str(c["id"]), text=texto)
            self._ids_historico.append(c["id"])

        if not conversas:
            self._mensagem_visualizacao("Nenhuma conversa encontrada.")

    def _conversa_selecionada(self):
        sel = self.lista_hist.selection()
        return int(sel[0]) if sel else None

    def _mensagem_visualizacao(self, texto):
        self._placeholder_texto(self.txt_visualizacao, texto)

    def _estado_botoes_historico(self, selecionado, tipo=None):
        """Habilita/desabilita as ações conforme o item selecionado e troca o texto
        do botão principal: 'Continuar conversa' para perguntas, 'Abrir resumo' para resumos."""
        estado = "normal" if selecionado else "disabled"
        self.btn_renomear.config(state=estado)
        self.btn_excluir.config(state=estado)
        if tipo == "resumo":
            self.btn_abrir.config(text="⬆  Abrir resumo", state=estado)
        else:
            self.btn_abrir.config(text="→  Continuar conversa", state=estado)

    def _mostrar_conversa_selecionada(self):
        conversa_id = self._conversa_selecionada()
        if conversa_id is None:
            self._estado_botoes_historico(selecionado=False)
            return
        try:
            conversa = db.buscar_conversa(conversa_id)
            mensagens = db.listar_mensagens(conversa_id)
        except Exception as e:
            self._mensagem_visualizacao(f"Erro ao carregar a conversa:\n{e}")
            self._estado_botoes_historico(selecionado=False)
            return
        self._renderizar_mensagens(self.txt_visualizacao, mensagens, conversa["tipo"])
        self._estado_botoes_historico(selecionado=True, tipo=conversa["tipo"])

    def _abrir_conversa_selecionada(self):
        conversa_id = self._conversa_selecionada()
        if conversa_id is None:
            messagebox.showinfo("Histórico", "Selecione uma conversa na lista.")
            return
        try:
            conversa = db.buscar_conversa(conversa_id)
            documento = db.buscar_documento(conversa["documento_id"])
            mensagens = db.listar_mensagens(conversa_id)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir a conversa:\n{e}")
            return

        # Recarrega o documento da conversa
        self.documento_id = documento["id"]
        self.texto_pdf    = documento["texto_extraido"] or ""
        self.nome_arquivo = documento["nome_arquivo"]
        self.lbl_arquivo.config(text=self.nome_arquivo, fg=COR_TEXTO)
        self.info_paginas[1].config(text=str(documento["paginas"] or "—"))
        self.info_chars[1].config(text=f"{len(self.texto_pdf):,}")
        if conversa["modo"] in nomes_dos_modos():
            self.modo_var.set(conversa["modo"])
            self._atualizar_descricao_modo()

        if conversa["tipo"] == "resumo":
            self._escrever_texto(self.txt_resumo, mensagens[0]["conteudo"] if mensagens else "")
            self.notebook.select(0)
            self._status(f"Resumo aberto: {self.nome_arquivo}", COR_SUCESSO)
            return

        # Conversa de perguntas: continua de onde parou
        self.conversa_id = conversa_id
        self.mensagens = [(m["papel"], m["conteudo"]) for m in mensagens]
        self._renderizar_mensagens(self.txt_historico, mensagens, "perguntas")
        self.notebook.select(1)
        self._status(f"Conversa aberta: {conversa['titulo']}", COR_SUCESSO)

    def _renomear_conversa_selecionada(self):
        conversa_id = self._conversa_selecionada()
        if conversa_id is None:
            return
        atual = self.lista_hist.item(str(conversa_id), "text").split("\n")[0][2:].strip()
        novo = simpledialog.askstring("Renomear", "Novo título:", initialvalue=atual, parent=self.root)
        if novo and novo.strip():
            try:
                db.renomear_conversa(conversa_id, novo)
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível renomear:\n{e}")
                return
            self._atualizar_historico()
            if str(conversa_id) in self.lista_hist.get_children():
                self.lista_hist.selection_set(str(conversa_id))

    def _excluir_conversa_selecionada(self):
        conversa_id = self._conversa_selecionada()
        if conversa_id is None:
            return
        if not messagebox.askyesno("Excluir", "Excluir esta conversa do histórico?\nO documento não será apagado."):
            return
        try:
            db.excluir_conversa(conversa_id)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível excluir:\n{e}")
            return
        if conversa_id == self.conversa_id:
            self._nova_conversa()
        self._atualizar_historico()
        self._mensagem_visualizacao("Conversa excluída.")

    def _renderizar_mensagens(self, widget, mensagens, tipo):
        """Mostra uma lista de mensagens do banco num widget Text já configurado."""
        widget.config(state="normal", fg=COR_TEXTO)
        widget.delete("1.0", "end")
        for i, m in enumerate(mensagens):
            if i:
                widget.insert("end", "\n")
            if m["papel"] == "usuario":
                widget.insert("end", "Você\n", ("user_label",))
                self._inserir_bloco_formatado(widget, m["conteudo"], "user_texto")
                widget.insert("end", "\n")
            else:
                rotulo = "Resumo" if tipo == "resumo" else "DocMind"
                widget.insert("end", f"{rotulo}\n", ("ia_label",))
                self._inserir_bloco_formatado(widget, m["conteudo"], "ia_texto")
                meta = " • ".join(x for x in (m["api"], f"modo {m['modo']}" if m["modo"] else None) if x)
                if meta:
                    widget.insert("end", f"\nvia {meta}", ("ia_meta",))
                widget.insert("end", "\n")
        widget.see("end" if widget is not self.txt_visualizacao else "1.0")
        widget.config(state="disabled")

    # ── Formatação de texto rico (sem markdown cru) ───────────
    def _configurar_tags_texto(self, widget, prefixo):
        """Tags usadas para renderizar negrito/listas de forma limpa num Text comum."""
        widget.tag_configure(f"{prefixo}_texto", font=FONTE_TEXTO, foreground=COR_TEXTO, spacing3=4)
        widget.tag_configure(f"{prefixo}_texto_negrito", font=("Inter", 11, "bold"), foreground=COR_TEXTO)
        widget.tag_configure(f"{prefixo}_erro", font=FONTE_TEXTO, foreground=COR_ERRO, spacing3=4)
        widget.tag_configure(f"{prefixo}_erro_negrito", font=("Inter", 11, "bold"), foreground=COR_ERRO)

    def _configurar_tags_chat(self, widget):
        widget.tag_configure("user_label", font=("Inter", 9, "bold"), foreground=COR_ACENTO, spacing1=14, spacing3=3)
        widget.tag_configure("user_texto", font=FONTE_TEXTO, foreground=COR_TEXTO, lmargin1=6, lmargin2=6, spacing3=4)
        widget.tag_configure("user_texto_negrito", font=("Inter", 11, "bold"), foreground=COR_TEXTO, lmargin1=6, lmargin2=6)

        widget.tag_configure("ia_label", font=("Inter", 9, "bold"), foreground=COR_ACENTO2, spacing1=8, spacing3=3)
        widget.tag_configure("ia_texto", font=FONTE_TEXTO, foreground=COR_TEXTO, lmargin1=6, lmargin2=6, spacing3=2)
        widget.tag_configure("ia_texto_negrito", font=("Inter", 11, "bold"), foreground=COR_TEXTO, lmargin1=6, lmargin2=6)
        widget.tag_configure("ia_pendente", font=("Inter", 11, "italic"), foreground=COR_TEXTO2, lmargin1=6, lmargin2=6)
        widget.tag_configure("ia_erro", font=FONTE_TEXTO, foreground=COR_ERRO, lmargin1=6, lmargin2=6, spacing3=2)
        widget.tag_configure("ia_erro_negrito", font=("Inter", 11, "bold"), foreground=COR_ERRO, lmargin1=6, lmargin2=6)
        widget.tag_configure("ia_meta", font=("Inter", 8), foreground=COR_TEXTO2, spacing3=10)

    def _inserir_com_negrito(self, widget, texto, tag_base, pos="end"):
        """Insere um trecho de texto trocando **negrito** por negrito real (sem os asteriscos)."""
        partes = re.split(r'(\*\*[^*]+\*\*)', texto)
        for parte in partes:
            if not parte:
                continue
            if parte.startswith("**") and parte.endswith("**") and len(parte) > 4:
                widget.insert(pos, parte[2:-2], (tag_base, f"{tag_base}_negrito"))
            else:
                widget.insert(pos, parte, (tag_base,))

    def _inserir_bloco_formatado(self, widget, texto, tag_base, pos="end"):
        """Insere um bloco de texto multi-linha, convertendo listas com '-'/'*' em bullets
        reais e negrito **markdown** em negrito de verdade, sem símbolos crus na tela."""
        linhas = texto.split("\n")
        for i, linha in enumerate(linhas):
            stripped = linha.strip()
            if stripped.startswith("* ") or stripped.startswith("- "):
                widget.insert(pos, "   •  ", (tag_base,))
                self._inserir_com_negrito(widget, stripped[2:].strip(), tag_base, pos)
            elif re.match(r'^\d+[\.\)]\s', stripped):
                widget.insert(pos, "   ", (tag_base,))
                self._inserir_com_negrito(widget, stripped, tag_base, pos)
            elif stripped.startswith("#"):
                titulo = stripped.lstrip("#").strip()
                widget.insert(pos, titulo, (tag_base, f"{tag_base}_negrito"))
            else:
                self._inserir_com_negrito(widget, linha, tag_base, pos)
            if i < len(linhas) - 1:
                widget.insert(pos, "\n")

    # ── Chat de perguntas ──────────────────────────────────────
    def _iniciar_pergunta_no_historico(self, pergunta):
        self.txt_historico.config(state="normal")
        if self.txt_historico.index("end-1c") != "1.0":
            self.txt_historico.insert("end", "\n")
        self.txt_historico.insert("end", "Você\n", ("user_label",))
        self._inserir_bloco_formatado(self.txt_historico, pergunta, "user_texto")
        self.txt_historico.insert("end", "\n")
        self.txt_historico.insert("end", "DocMind\n", ("ia_label",))
        self.txt_historico.mark_set("resp_ini", "end-1c")
        self.txt_historico.mark_gravity("resp_ini", "left")
        self.txt_historico.insert("end", "Consultando a IA...", ("ia_pendente",))
        self.txt_historico.mark_set("resp_fim", "end-1c")
        self.txt_historico.mark_gravity("resp_fim", "right")
        self.txt_historico.see("end")
        self.txt_historico.config(state="disabled")

    def _concluir_resposta_no_historico(self, texto, nome_api=None, erro=False):
        self.txt_historico.config(state="normal")
        self.txt_historico.delete("resp_ini", "resp_fim")
        self.txt_historico.mark_set("insert", "resp_ini")

        tag_base = "ia_erro" if erro else "ia_texto"
        self._inserir_bloco_formatado(self.txt_historico, texto, tag_base, pos="insert")

        if nome_api and not erro:
            self.txt_historico.insert("insert", f"\nvia {nome_api}", ("ia_meta",))

        self.txt_historico.mark_unset("resp_ini")
        self.txt_historico.mark_unset("resp_fim")
        self.txt_historico.see("end")
        self.txt_historico.config(state="disabled")

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

    def _escrever_texto(self, widget, texto, erro=False):
        widget.config(state="normal", fg=COR_TEXTO)
        widget.delete("1.0", "end")
        self._inserir_bloco_formatado(widget, texto, "resumo_erro" if erro else "resumo_texto")
        widget.config(state="disabled")

    def _limpar_historico(self):
        self.txt_historico.config(state="normal")
        self.txt_historico.delete("1.0", "end")
        self.txt_historico.config(state="disabled")

    def _verificar_api(self):
        if ANTHROPIC_API_KEY:
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