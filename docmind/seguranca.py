"""Proteções contra uso indevido: prompt injection, comandos maliciosos,
pedidos inadequados e tentativas de redefinir a identidade da IA."""

import re

# Padrões que indicam tentativas maliciosas
PADROES_BLOQUEADOS = [
    # Prompt Injection — tentativas de sobrescrever o sistema
    r"ignore (todas as|as|suas) (instru[çc][oõ]es|regras)",
    r"esque[çc]a\s+tudo|esquece?[- ]?tudo",
    r"\bnovo\s+prompt\b",
    r"(assuma|adote|use|siga|aceite|receba)\s+(um|o|este|esse|esta|essa)?\s*nov[oa]\s+"
    r"(sistema|papel|role|persona|identidade)",
    r"system\s*prompt",
    r"\bact(ing)? as (an?|if|my)\b",
    r"ignore previous",
    r"jailbreak",
    r"dan mode",
    r"pretend (you are|to be)",

    # Comandos maliciosos (exige sintaxe de código, não só a palavra)
    r"\b(exec|eval)\s*\(|\bos\.(system|popen|remove|environ)|\bsubprocess\b",
    r"(delete|drop|truncate)\s+(table|database|all)",
    r"rm\s+-rf",
    r"format\s+c:",

    # Pedidos inadequados (o pedido em si, não o assunto do documento:
    # "o que a lei diz sobre tráfico de drogas?" é uma pergunta legítima)
    r"(como|how to).{0,30}(hackear|invadir|roubar|matar|bomb)",
    r"(como|onde)\s+(comprar|vender|fabricar|produzir|conseguir).{0,25}(droga|arma)",

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
