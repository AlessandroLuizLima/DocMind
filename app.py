# ═══════════════════════════════════════════════════════════════
# DocMind — Interface Gráfica (Tkinter)
# Dark mode | Importar PDF | Resumo via IA | Perguntas e Respostas
# ═══════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import sys
import re
import ctypes

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
from langchain_core.prompts import ChatPromptTemplate
import PyPDF2

# Importa a lógica de IA (modos, segurança e roteamento) do DocMindAPI
from DocMindAPI import MODOS, verificar_seguranca, escolher_api, claude

# Importa funções do banco de dados
try:
    from database.database import inserir_documento, inserir_resumo, inserir_pergunta
    DB_DISPONIVEL = True
except Exception:
    DB_DISPONIVEL = False

# ── Configuração da API ──────────────────────────────────────
load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")

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
# COMPONENTES DE UI REUTILIZÁVEIS (tooltip + campo com máscara)
# ═══════════════════════════════════════════════════════════════

class Tooltip:
    """Dica de contexto que aparece ao passar o mouse sobre um widget."""

    def __init__(self, widget, texto):
        self.widget = widget
        self.texto = texto
        self.janela = None
        widget.bind("<Enter>", self._mostrar)
        widget.bind("<Leave>", self._esconder)
        widget.bind("<ButtonPress>", self._esconder)

    def _mostrar(self, event=None):
        if self.janela or not self.texto:
            return
        x = self.widget.winfo_rootx() + 4
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.janela = tk.Toplevel(self.widget)
        self.janela.wm_overrideredirect(True)
        self.janela.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.janela, text=self.texto, font=FONTE_PEQUENA,
            fg=COR_TEXTO, bg=COR_PAINEL, bd=1, relief="solid",
            padx=8, pady=5, wraplength=240, justify="left"
        ).pack()

    def _esconder(self, event=None):
        if self.janela:
            self.janela.destroy()
            self.janela = None


class CampoNumerico(tk.Entry):
    """Entry que só aceita dígitos — máscara numérica usada no intervalo de páginas."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.bind("<KeyRelease>", self._filtrar)

    def _filtrar(self, event):
        if event.keysym in ("BackSpace", "Delete", "Left", "Right", "Tab", "Shift_L", "Shift_R"):
            return
        digitos = re.sub(r"\D", "", self.get())[:4]
        if digitos != self.get():
            pos = self.index("insert")
            self.delete(0, "end")
            self.insert(0, digitos)
            self.icursor(min(pos, len(digitos)))


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES DE IA
# ═══════════════════════════════════════════════════════════════

def extrair_paginas_pdf(caminho):
    """Extrai o texto de cada página do PDF separadamente, como uma lista."""
    paginas = []
    with open(caminho, "rb") as f:
        leitor = PyPDF2.PdfReader(f)
        for pagina in leitor.pages:
            paginas.append((pagina.extract_text() or "").strip())
    return paginas


def _instrucao_do_modo(modo_nome):
    """Busca a instrução de sistema correspondente ao nome do modo selecionado."""
    chave = next((k for k, v in MODOS.items() if v["nome"] == modo_nome), "4")
    return MODOS[chave]["instrucao"]


def gerar_resumo(texto_pdf, modo_nome="Detalhado"):
    """Envia o texto para a API do Claude e retorna o resumo, aplicando o modo selecionado."""
    instrucao_modo = _instrucao_do_modo(modo_nome)

    prompt = ChatPromptTemplate.from_template(
        "{instrucao_modo}\n\n"
        "Você é o DocMind, assistente especializado em documentos PDF.\n"
        "Responda sempre em português.\n\n"
        "Resuma o documento abaixo seguindo o estilo definido acima. "
        "Use tópicos claros quando fizer sentido para o modo escolhido.\n\n"
        "Documento:\n{texto}"
    )
    chain = prompt | claude
    resposta = chain.invoke({"instrucao_modo": instrucao_modo, "texto": texto_pdf[:12000]})
    return resposta.content


def responder_pergunta(texto_pdf, pergunta, modo_nome="Detalhado"):
    """Responde uma pergunta com base no conteúdo do PDF, aplicando modo,
    verificação de segurança e roteamento entre Claude/Gemini."""
    bloqueado, _ = verificar_seguranca(pergunta)
    if bloqueado:
        return "Sua pergunta contém conteúdo não permitido. Reformule, por favor.", None

    instrucao_modo = _instrucao_do_modo(modo_nome)
    modelo, nome_api = escolher_api(pergunta)

    prompt = ChatPromptTemplate.from_template(
        "{instrucao_modo}\n\n"
        "Você é o DocMind, assistente especializado em análise de documentos PDF.\n"
        "Responda com base no texto abaixo. Se a informação não estiver no documento, diga claramente.\n"
        "Responda em português de forma objetiva.\n\n"
        "Documento:\n{texto}\n\n"
        "Pergunta: {pergunta}"
    )
    chain = prompt | modelo
    resposta = chain.invoke({
        "instrucao_modo": instrucao_modo,
        "texto": texto_pdf[:12000],
        "pergunta": pergunta
    })
    return resposta.content, nome_api


# ═══════════════════════════════════════════════════════════════
# INTERFACE GRÁFICA
# ═══════════════════════════════════════════════════════════════

class DocMindApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DocMind")
        self.root.geometry("980x760")
        self.root.minsize(820, 640)
        self.root.configure(bg=COR_BG)

        self.paginas_pdf  = []   # lista com o texto de cada página do PDF atual
        self.texto_pdf    = ""   # texto completo (todas as páginas), usado nas Perguntas
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
        Tooltip(self.lbl_api, "Mostra se a chave da API do Claude foi encontrada no .env. Sem isso, a geração de resumo não funciona.")
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

        btn_importar = self._botao(
            self.sidebar, "Importar PDF",
            self._importar_pdf, icone="📂"
        )
        btn_importar.pack(fill="x", padx=16, pady=(0, 6))
        Tooltip(btn_importar, "Selecione um arquivo .pdf do seu computador para começar a análise.")

        # Intervalo de páginas (campo com máscara numérica, uso real no resumo)
        tk.Label(
            self.sidebar, text="Resumir páginas (opcional)",
            font=FONTE_PEQUENA, fg=COR_TEXTO2, bg=COR_PAINEL
        ).pack(anchor="w", padx=16, pady=(2, 2))

        frame_intervalo = tk.Frame(self.sidebar, bg=COR_PAINEL)
        frame_intervalo.pack(fill="x", padx=16, pady=(0, 6))

        self.campo_pag_inicio = CampoNumerico(
            frame_intervalo, width=5, justify="center",
            font=FONTE_TEXTO, fg=COR_TEXTO, bg=COR_ENTRADA,
            relief="flat", bd=0, insertbackground=COR_ACENTO
        )
        self.campo_pag_inicio.pack(side="left", ipady=6)

        tk.Label(
            frame_intervalo, text="até",
            font=FONTE_PEQUENA, fg=COR_TEXTO2, bg=COR_PAINEL
        ).pack(side="left", padx=6)

        self.campo_pag_fim = CampoNumerico(
            frame_intervalo, width=5, justify="center",
            font=FONTE_TEXTO, fg=COR_TEXTO, bg=COR_ENTRADA,
            relief="flat", bd=0, insertbackground=COR_ACENTO
        )
        self.campo_pag_fim.pack(side="left", ipady=6)

        Tooltip(
            frame_intervalo,
            "Restringe o resumo a um intervalo de páginas do PDF (ex: 5 até 20), "
            "útil em documentos longos. Deixe os dois em branco para resumir o documento inteiro."
        )

        btn_resumo = self._botao(
            self.sidebar, "Gerar Resumo",
            self._gerar_resumo, icone="✦", cor=COR_ACENTO2
        )
        btn_resumo.pack(fill="x", padx=16, pady=(4, 16))
        Tooltip(btn_resumo, "Envia o texto extraído do PDF (ou só o intervalo de páginas informado) para a IA, no modo selecionado abaixo.")

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
        Tooltip(
            self.info_db[1],
            "Indica se a conexão com o banco PostgreSQL foi estabelecida. "
            "Se estiver desconectado, o app continua funcionando, mas o histórico não é salvo."
        )

        # Separador
        tk.Frame(self.sidebar, bg=COR_BORDA, height=1).pack(fill="x", padx=16, pady=8)

        # Seção: modo
        self._secao_label(self.sidebar, "MODO DA IA")
        self.modo_var = tk.StringVar(value="Detalhado")
        for chave, modo in MODOS.items():
            rb = tk.Radiobutton(
                self.sidebar, text=modo["nome"],
                variable=self.modo_var, value=modo["nome"],
                font=FONTE_PEQUENA, fg=COR_TEXTO, bg=COR_PAINEL,
                selectcolor=COR_ENTRADA, activebackground=COR_PAINEL,
                activeforeground=COR_ACENTO, cursor="hand2"
            )
            rb.pack(anchor="w", padx=20, pady=1)
            Tooltip(rb, modo["instrucao"])

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
        Tooltip(self.entrada_pergunta, "Digite uma pergunta sobre o conteúdo do PDF importado e pressione Enter ou clique em Perguntar.")

        btn_perguntar = self._botao(
            frame_entrada, "Perguntar",
            self._fazer_pergunta, icone="→"
        )
        btn_perguntar.pack(side="right")
        Tooltip(btn_perguntar, "Envia a pergunta para a IA, usando o modo selecionado na barra lateral. Considera o documento inteiro, não o intervalo de páginas.")

    # ── Ações ────────────────────────────────────────────────
    def _importar_pdf(self):
        caminho = filedialog.askopenfilename(
            title="Selecione um PDF",
            filetypes=[("Arquivos PDF", "*.pdf")]
        )
        if not caminho:
            return

        # Validação de dados inválidos: garante que o arquivo é realmente um PDF
        if not caminho.lower().endswith(".pdf"):
            messagebox.showerror("Arquivo inválido", "Selecione um arquivo com extensão .pdf.")
            return

        self._status("Lendo PDF...", COR_ACENTO2)
        try:
            self.paginas_pdf   = extrair_paginas_pdf(caminho)
            self.texto_pdf     = "\n".join(self.paginas_pdf).strip()
            self.nome_arquivo  = os.path.basename(caminho)
            num_paginas        = len(self.paginas_pdf)

            # Validação de dados inválidos: PDF sem texto extraível (ex: escaneado sem OCR)
            if not self.texto_pdf:
                messagebox.showwarning(
                    "Aviso",
                    "Não foi possível extrair texto deste PDF.\n"
                    "Ele pode ser uma imagem escaneada sem OCR — o resumo pode não funcionar corretamente."
                )

            # Limpa o intervalo de páginas do documento anterior
            self.campo_pag_inicio.delete(0, "end")
            self.campo_pag_fim.delete(0, "end")

            # Atualiza sidebar
            self.lbl_arquivo.config(text=self.nome_arquivo, fg=COR_TEXTO)
            self.info_paginas[1].config(text=str(num_paginas))
            self.info_chars[1].config(text=f"{len(self.texto_pdf):,}")

            # Salva no banco — tratamento de erro de conexão/acesso ao banco
            self.documento_id = None
            if DB_DISPONIVEL:
                try:
                    self.documento_id = inserir_documento(
                        self.nome_arquivo, caminho, self.texto_pdf, num_paginas
                    )
                except Exception as e:
                    self._status(f"PDF carregado, mas falha ao salvar no banco: {e}", COR_ERRO)

            self._placeholder_texto(
                self.txt_resumo,
                f"PDF '{self.nome_arquivo}' carregado com sucesso.\nClique em 'Gerar Resumo' para continuar."
            )
            self._limpar_historico()
            if self.documento_id is not None or not DB_DISPONIVEL:
                self._status(f"PDF carregado: {self.nome_arquivo}", COR_SUCESSO)

        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível ler o PDF:\n{e}")
            self._status("Erro ao ler PDF", COR_ERRO)

    def _validar_intervalo_paginas(self):
        """Valida o intervalo de páginas informado.
        Retorna (ok, inicio_ou_None, fim_ou_None, mensagem_erro_ou_None)."""
        ini_txt = self.campo_pag_inicio.get().strip()
        fim_txt = self.campo_pag_fim.get().strip()

        if not ini_txt and not fim_txt:
            return True, None, None, None  # nenhum intervalo informado = documento inteiro

        if not ini_txt or not fim_txt:
            return False, None, None, "Preencha as duas páginas do intervalo (início e fim), ou deixe ambas em branco."

        inicio, fim = int(ini_txt), int(fim_txt)
        total_paginas = len(self.paginas_pdf)

        if inicio < 1 or fim < 1:
            return False, None, None, "As páginas devem ser maiores que 0."
        if inicio > fim:
            return False, None, None, "A página inicial não pode ser maior que a final."
        if total_paginas and fim > total_paginas:
            return False, None, None, f"O documento tem {total_paginas} página(s) — o intervalo não pode ultrapassar isso."

        return True, inicio, fim, None

    def _gerar_resumo(self):
        if not self.texto_pdf:
            messagebox.showwarning("Atenção", "Importe um PDF primeiro.")
            return

        # Validação de dados inválidos: intervalo de páginas precisa ser coerente
        ok, pag_inicio, pag_fim, erro_msg = self._validar_intervalo_paginas()
        if not ok:
            messagebox.showerror("Intervalo inválido", erro_msg)
            return

        if pag_inicio and pag_fim:
            texto_para_resumo = "\n".join(self.paginas_pdf[pag_inicio - 1:pag_fim]).strip()
            if not texto_para_resumo:
                messagebox.showwarning("Aviso", "Não há texto extraível nas páginas selecionadas.")
                return
            descricao_intervalo = f" (páginas {pag_inicio}–{pag_fim})"
        else:
            texto_para_resumo = self.texto_pdf
            descricao_intervalo = ""

        modo_nome = self.modo_var.get()
        self._status(f"Gerando resumo{descricao_intervalo} — modo {modo_nome}...", COR_ACENTO)
        self._placeholder_texto(self.txt_resumo, "Consultando a IA, aguarde...")

        def tarefa():
            try:
                resumo = gerar_resumo(texto_para_resumo, modo_nome)
                self.root.after(0, lambda: self._escrever_texto(self.txt_resumo, resumo))
                self.root.after(0, lambda: self._status("Resumo gerado!", COR_SUCESSO))

                if DB_DISPONIVEL and self.documento_id:
                    try:
                        inserir_resumo(self.documento_id, resumo, 0, 0)
                    except Exception as e:
                        self.root.after(0, lambda: self._status(f"Resumo gerado, mas falha ao salvar no banco: {e}", COR_ERRO))

            except Exception as e:
                # Tratamento de erro de conexão/acesso à API de IA
                self.root.after(0, lambda: self._escrever_texto(
                    self.txt_resumo, f"Erro ao consultar a IA:\n{e}", erro=True
                ))
                self.root.after(0, lambda: self._status("Erro na API", COR_ERRO))

        threading.Thread(target=tarefa, daemon=True).start()

    def _fazer_pergunta(self):
        pergunta = self.entrada_pergunta.get().strip()

        # Validação de dados inválidos: pergunta vazia
        if not pergunta:
            messagebox.showwarning("Atenção", "Digite uma pergunta antes de enviar.")
            return
        if not self.texto_pdf:
            messagebox.showwarning("Atenção", "Importe um PDF antes de fazer perguntas.")
            return

        modo_nome = self.modo_var.get()
        self.entrada_pergunta.delete(0, "end")
        self._status("Consultando a IA...", COR_ACENTO)
        self._iniciar_pergunta_no_historico(pergunta)
        self.notebook.select(1)

        def tarefa():
            try:
                resposta, nome_api = responder_pergunta(self.texto_pdf, pergunta, modo_nome)
                self.root.after(0, lambda: self._concluir_resposta_no_historico(resposta, nome_api))
                self.root.after(0, lambda: self._status("Resposta recebida!", COR_SUCESSO))

                if DB_DISPONIVEL and self.documento_id:
                    try:
                        inserir_pergunta(self.documento_id, pergunta, resposta, 0, 0)
                    except Exception as e:
                        self.root.after(0, lambda: self._status(f"Resposta recebida, mas falha ao salvar no banco: {e}", COR_ERRO))

            except Exception as e:
                # Tratamento de erro de conexão/acesso à API de IA
                self.root.after(0, lambda: self._concluir_resposta_no_historico(str(e), erro=True))
                self.root.after(0, lambda: self._status("Erro na API", COR_ERRO))

        threading.Thread(target=tarefa, daemon=True).start()

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