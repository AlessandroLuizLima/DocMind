# ═══════════════════════════════════════════════════════════════
# DocMind — Engenharia de Prompts Avançada
# ═══════════════════════════════════════════════════════════════
#
# Implementações desta versão:
#
# 1. MODOS DA IA
#    Cinco modos de resposta selecionáveis pelo usuário:
#    técnico, resumido, professor, detalhado, suporte técnico
#
# 2. TIPOS DE PROMPT
#    - Prompt Simples: pergunta direta sem estrutura extra
#    - Prompt Estruturado: com contexto + pergunta + formato esperado
#    - Prompt Especializado: com papel, restrições e exemplos definidos
#
# 3. PROTEÇÕES
#    - Prompt Injection: detecta tentativas de sobrescrever o sistema
#    - Comandos maliciosos: bloqueia instruções perigosas
#    - Pedidos inadequados: filtra conteúdo impróprio
#    - Quebra de regras: impede redefinição de identidade da IA
#
# 4. DUAS APIs
#    - Claude (Anthropic) via LangChain → responde perguntas sobre documentos
#    - Gemini (Google) via LangChain    → responde perguntas gerais / comparações
#    O sistema decide qual API usar com base na pergunta do usuário
#
# ═══════════════════════════════════════════════════════════════

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
import os
import re

# ── Carrega as chaves do .env ────────────────────────────────
load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY    = os.getenv("GOOGLE_API_KEY")


# ═══════════════════════════════════════════════════════════════
# 1. MODELOS
# ═══════════════════════════════════════════════════════════════

# Claude — especialista em documentos PDF
claude = ChatAnthropic(
    model="claude-sonnet-4-6",
    anthropic_api_key=ANTHROPIC_API_KEY,
    temperature=0.5
)

# Gemini — perguntas gerais e comparações
gemini = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    api_key=GOOGLE_API_KEY,
    temperature=0.7
)


# ═══════════════════════════════════════════════════════════════
# 2. MODOS DA IA
# Cada modo define como a IA deve se comportar ao responder
# ═══════════════════════════════════════════════════════════════

MODOS = {
    "1": {
        "nome": "Técnico",
        "instrucao": (
            "Você é um assistente técnico especializado. "
            "Use terminologia precisa, cite detalhes técnicos relevantes, "
            "estruture a resposta com tópicos quando necessário. "
            "Evite simplificações excessivas."
        )
    },
    "2": {
        "nome": "Resumido",
        "instrucao": (
            "Você é um assistente objetivo. "
            "Responda em no máximo 3 linhas, de forma direta e sem rodeios. "
            "Vá direto ao ponto."
        )
    },
    "3": {
        "nome": "Professor",
        "instrucao": (
            "Você é um professor didático e paciente. "
            "Explique como se o usuário fosse um iniciante no assunto. "
            "Use exemplos simples, analogias e linguagem acessível. "
            "Incentive o aprendizado."
        )
    },
    "4": {
        "nome": "Detalhado",
        "instrucao": (
            "Você é um assistente completo e minucioso. "
            "Forneça uma resposta aprofundada, cobrindo todos os ângulos do tema. "
            "Inclua contexto, explicações, exemplos e possíveis desdobramentos."
        )
    },
    "5": {
        "nome": "Suporte Técnico",
        "instrucao": (
            "Você é um agente de suporte técnico experiente. "
            "Identifique o problema relatado, liste possíveis causas "
            "e forneça um passo a passo claro para resolução. "
            "Seja empático e preciso."
        )
    }
}


# ═══════════════════════════════════════════════════════════════
# 3. TIPOS DE PROMPT
# ═══════════════════════════════════════════════════════════════

def prompt_simples(instrucao_modo):
    """
    Prompt Simples — pergunta direta com papel da IA definido.
    Ideal para consultas rápidas sem contexto adicional.
    """
    return ChatPromptTemplate.from_template(
        "{instrucao_modo}\n\n"
        "Responda em português.\n\n"
        "Pergunta: {pergunta}"
    )


def prompt_estruturado(instrucao_modo):
    """
    Prompt Estruturado — inclui contexto, pergunta e formato esperado.
    Ideal para análise de documentos com informações de contexto.
    """
    return ChatPromptTemplate.from_template(
        "{instrucao_modo}\n\n"
        "Responda sempre em português.\n\n"
        "## Contexto\n"
        "{contexto}\n\n"
        "## Pergunta\n"
        "{pergunta}\n\n"
        "## Formato esperado da resposta\n"
        "- Comece com uma resposta direta\n"
        "- Em seguida, explique o raciocínio\n"
        "- Se houver dados numéricos, destaque-os\n"
        "- Finalize com uma conclusão breve"
    )


def prompt_especializado(instrucao_modo):
    """
    Prompt Especializado — papel definido, restrições e exemplos.
    Ideal para garantir respostas dentro do escopo do DocMind.
    """
    return ChatPromptTemplate.from_template(
        "{instrucao_modo}\n\n"
        "Você é o DocMind, assistente especializado em documentos PDF.\n\n"
        "## Regras obrigatórias\n"
        "- Responda APENAS com base no conteúdo de documentos\n"
        "- Se a informação não estiver no documento, diga claramente\n"
        "- Nunca invente dados, valores ou datas\n"
        "- Responda sempre em português\n\n"
        "## Exemplo de boa resposta\n"
        "Pergunta: Qual é o prazo do contrato?\n"
        "Resposta: Conforme o documento, o prazo é de 90 dias corridos a partir da assinatura.\n\n"
        "## Pergunta do usuário\n"
        "{pergunta}"
    )


# ═══════════════════════════════════════════════════════════════
# 4. PROTEÇÕES CONTRA USO INDEVIDO
# ═══════════════════════════════════════════════════════════════

# Padrões que indicam tentativas maliciosas
PADROES_BLOQUEADOS = [
    # Prompt Injection — tentativas de sobrescrever o sistema
    r"ignore (todas as|as|suas) (instru[çc][oõ]es|regras)",
    r"esquece?[- ]?tudo",
    r"novo (prompt|sistema|papel|role|contexto)",
    r"system\s*prompt",
    r"act as",
    r"ignore previous",
    r"jailbreak",
    r"dan mode",
    r"pretend (you are|to be)",

    # Comandos maliciosos
    r"\bexec\b|\beval\b|\bos\.|\bsubprocess\b",
    r"(delete|drop|truncate)\s+(table|database|all)",
    r"rm\s+-rf",
    r"format\s+c:",

    # Pedidos inadequados
    r"(como|how to).{0,30}(hackear|invadir|roubar|matar|bomb)",
    r"(droga|tráfico|arma\s+ilegal)",

    # Quebra de regras / redefinição de identidade
    r"voc[eê]\s+(não\s+é|agora\s+é|passa\s+a\s+ser)",
    r"(mude|altere|troque)\s+(seu|sua)\s+(papel|identidade|personalidade)",
    r"finja\s+que",
]


def verificar_seguranca(texto):
    """
    Verifica se a entrada contém padrões bloqueados.
    Retorna (True, motivo) se bloqueado, (False, None) se seguro.
    """
    texto_lower = texto.lower()
    for padrao in PADROES_BLOQUEADOS:
        if re.search(padrao, texto_lower):
            return True, padrao
    return False, None


# ═══════════════════════════════════════════════════════════════
# 5. ROTEADOR — decide qual API responde
# ═══════════════════════════════════════════════════════════════

PALAVRAS_DOCUMENTO = [
    "documento", "pdf", "contrato", "arquivo", "texto", "cláusula",
    "anexo", "relatório", "planilha", "formulário", "resumo do arquivo"
]

def escolher_api(pergunta):
    """
    Roteador simples:
    - Se a pergunta menciona documentos/PDFs → Claude
    - Caso contrário → Gemini
    Retorna (modelo, nome_api)
    """
    pergunta_lower = pergunta.lower()
    for palavra in PALAVRAS_DOCUMENTO:
        if palavra in pergunta_lower:
            return claude, "Claude (Anthropic) — especialista em documentos"
    return gemini, "Gemini (Google) — perguntas gerais"


# ═══════════════════════════════════════════════════════════════
# 6. EXECUÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 58)
    print("  DocMind — Engenharia de Prompts")
    print("=" * 58)

    # ── Escolha do modo ─────────────────────────────────────
    print("\nEscolha o modo da IA:")
    for chave, modo in MODOS.items():
        print(f"  [{chave}] {modo['nome']}")

    escolha = input("\nModo (1-5): ").strip()
    if escolha not in MODOS:
        print("Modo inválido. Usando modo Resumido.")
        escolha = "2"

    modo_selecionado = MODOS[escolha]
    instrucao_modo   = modo_selecionado["instrucao"]
    print(f"\nModo ativo: {modo_selecionado['nome']}")

    # ── Escolha do tipo de prompt ────────────────────────────
    print("\nEscolha o tipo de prompt:")
    print("  [1] Simples      — pergunta direta")
    print("  [2] Estruturado  — com contexto e formato")
    print("  [3] Especializado — com regras e exemplos")

    tipo = input("\nTipo (1-3): ").strip()

    # ── Entrada do usuário ───────────────────────────────────
    pergunta = input("\nDigite sua pergunta: ").strip()

    # ── Verificação de segurança ─────────────────────────────
    bloqueado, motivo = verificar_seguranca(pergunta)
    if bloqueado:
        print("\n⚠️  Solicitação bloqueada por segurança.")
        print("   Sua mensagem contém conteúdo não permitido.")
        print("   Por favor, reformule sua pergunta.")
        exit(0)

    # ── Seleciona a API correta ──────────────────────────────
    modelo, nome_api = escolher_api(pergunta)
    print(f"\nAPI selecionada: {nome_api}")

    # ── Monta e executa o prompt ─────────────────────────────
    try:
        if tipo == "1":
            prompt = prompt_simples(instrucao_modo)
            chain  = prompt | modelo
            resposta = chain.invoke({
                "instrucao_modo": instrucao_modo,
                "pergunta": pergunta
            })

        elif tipo == "2":
            contexto = input("Informe o contexto do documento (ou Enter para pular): ").strip()
            if not contexto:
                contexto = "Nenhum contexto fornecido."
            prompt = prompt_estruturado(instrucao_modo)
            chain  = prompt | modelo
            resposta = chain.invoke({
                "instrucao_modo": instrucao_modo,
                "contexto": contexto,
                "pergunta": pergunta
            })

        else:
            prompt = prompt_especializado(instrucao_modo)
            chain  = prompt | modelo
            resposta = chain.invoke({
                "instrucao_modo": instrucao_modo,
                "pergunta": pergunta
            })

        print(f"\n{'─' * 58}")
        print(f"Resposta ({modo_selecionado['nome']}):\n")
        print(resposta.content)
        print(f"{'─' * 58}")

    except Exception as e:
        print(f"\n[ERRO] Falha ao consultar a API: {e}")