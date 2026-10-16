import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME", "docmind"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

def conectar():
    return psycopg2.connect(**DB_CONFIG)

def inserir_documento(nome_arquivo, caminho, texto_extraido, paginas):
    sql = """
        INSERT INTO documentos (nome_arquivo, caminho, texto_extraido, paginas)
        VALUES (%s, %s, %s, %s)
        RETURNING id;
    """
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (nome_arquivo, caminho, texto_extraido, paginas))
            return cur.fetchone()[0]


def inserir_resumo(documento_id, resumo_gerado, tokens_entrada, tokens_saida):
    sql = """
        INSERT INTO resumos (documento_id, resumo_gerado, tokens_entrada, tokens_saida)
        VALUES (%s, %s, %s, %s)
        RETURNING id;
    """
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (documento_id, resumo_gerado, tokens_entrada, tokens_saida))
            return cur.fetchone()[0]


def inserir_pergunta(documento_id, pergunta, resposta, tokens_entrada, tokens_saida):
    sql = """
        INSERT INTO perguntas (documento_id, pergunta, resposta, tokens_entrada, tokens_saida)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (documento_id, pergunta, resposta, tokens_entrada, tokens_saida))
            return cur.fetchone()[0]

def listar_documentos():
    sql = "SELECT id, nome_arquivo, paginas, data_upload FROM documentos ORDER BY data_upload DESC;"
    with conectar() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            return cur.fetchall()


def buscar_resumo(documento_id):
    sql = """
        SELECT resumo_gerado, data_geracao FROM resumos
        WHERE documento_id = %s ORDER BY data_geracao DESC LIMIT 1;
    """
    with conectar() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (documento_id,))
            return cur.fetchone()


def listar_perguntas(documento_id):
    sql = """
        SELECT pergunta, resposta, data_pergunta FROM perguntas
        WHERE documento_id = %s ORDER BY data_pergunta ASC;
    """
    with conectar() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (documento_id,))
            return cur.fetchall()
        

def criar_tabelas():
    """Cria as tabelas (se ainda não existirem) a partir do schema.sql."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        sql = f.read()
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def buscar_documento(documento_id):
    sql = """
        SELECT id, nome_arquivo, caminho, texto_extraido, paginas
        FROM documentos WHERE id = %s;
    """
    with conectar() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (documento_id,))
            return cur.fetchone()


# ── Histórico de conversas ───────────────────────────────────

def criar_conversa(documento_id, titulo, tipo="perguntas", modo=None):
    sql = """
        INSERT INTO conversas (documento_id, titulo, tipo, modo)
        VALUES (%s, %s, %s, %s)
        RETURNING id;
    """
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (documento_id, titulo[:200], tipo, modo))
            return cur.fetchone()[0]


def inserir_mensagem(conversa_id, papel, conteudo, modo=None, api=None):
    sql = """
        INSERT INTO mensagens (conversa_id, papel, conteudo, modo, api)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (conversa_id, papel, conteudo, modo, api))
            msg_id = cur.fetchone()[0]
            cur.execute(
                "UPDATE conversas SET data_atualizacao = NOW() WHERE id = %s;",
                (conversa_id,)
            )
            return msg_id


def listar_conversas(busca=None, tipo=None, limite=200):
    """Lista conversas e resumos, mais recentes primeiro.
    busca: filtra por título, nome do arquivo ou conteúdo das mensagens.
    tipo: 'perguntas', 'resumo' ou None (todos)."""
    padrao = None
    if busca and busca.strip():
        escapado = (busca.strip().replace("\\", "\\\\")
                    .replace("%", "\\%").replace("_", "\\_"))
        padrao = f"%{escapado}%"
    sql = """
        SELECT c.id, c.titulo, c.tipo, c.modo, c.documento_id,
               d.nome_arquivo, c.data_atualizacao,
               (SELECT COUNT(*) FROM mensagens m WHERE m.conversa_id = c.id) AS total_mensagens
        FROM conversas c
        JOIN documentos d ON d.id = c.documento_id
        WHERE (%(tipo)s::text IS NULL OR c.tipo = %(tipo)s::text)
          AND (%(padrao)s::text IS NULL
               OR c.titulo ILIKE %(padrao)s::text
               OR d.nome_arquivo ILIKE %(padrao)s::text
               OR EXISTS (SELECT 1 FROM mensagens m
                          WHERE m.conversa_id = c.id AND m.conteudo ILIKE %(padrao)s::text))
        ORDER BY c.data_atualizacao DESC
        LIMIT %(limite)s;
    """
    with conectar() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, {"tipo": tipo, "padrao": padrao, "limite": limite})
            return cur.fetchall()


def buscar_conversa(conversa_id):
    sql = """
        SELECT c.id, c.titulo, c.tipo, c.modo, c.documento_id, d.nome_arquivo
        FROM conversas c JOIN documentos d ON d.id = c.documento_id
        WHERE c.id = %s;
    """
    with conectar() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (conversa_id,))
            return cur.fetchone()


def listar_mensagens(conversa_id):
    sql = """
        SELECT papel, conteudo, modo, api, data_envio FROM mensagens
        WHERE conversa_id = %s ORDER BY id ASC;
    """
    with conectar() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (conversa_id,))
            return cur.fetchall()


def renomear_conversa(conversa_id, novo_titulo):
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE conversas SET titulo = %s WHERE id = %s;",
                        (novo_titulo.strip()[:200], conversa_id))


def excluir_conversa(conversa_id):
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM conversas WHERE id = %s;", (conversa_id,))


if __name__ == "__main__":
    print("=" * 50)
    print("  DocMind — Teste do Banco de Dados")
    print("=" * 50)

    print("\n[1] Testando conexão...")
    try:
        conn = conectar()
        conn.close()
        print("     Conexão OK!")
    except Exception as e:
        print(f"     ERRO: {e}")
        exit(1)

    print("\n[2] Inserindo documento de teste...")
    doc_id = inserir_documento(
        nome_arquivo   = "contrato_teste.pdf",
        caminho        = "C:/DocMind/contrato_teste.pdf",
        texto_extraido = "Contrato entre Empresa ABC e João Silva. Valor: R$ 15.000,00. Prazo: 90 dias.",
        paginas        = 3
    )
    print(f"     Documento salvo com ID {doc_id}")

    print("\n[3] Inserindo resumo de teste...")
    res_id = inserir_resumo(
        documento_id  = doc_id,
        resumo_gerado = "Contrato de R$ 15.000,00 entre Empresa ABC e João Silva, prazo de 90 dias.",
        tokens_entrada = 120,
        tokens_saida   = 40
    )
    print(f"     Resumo salvo com ID {res_id}")

    print("\n[4] Inserindo pergunta de teste...")
    per_id = inserir_pergunta(
        documento_id  = doc_id,
        pergunta      = "Qual é o valor do contrato?",
        resposta      = "O valor é R$ 15.000,00.",
        tokens_entrada = 90,
        tokens_saida   = 15
    )
    print(f"     Pergunta salva com ID {per_id}")

    print("\n[5] Listando documentos salvos:")
    for doc in listar_documentos():
        print(f"     ID {doc['id']} | {doc['nome_arquivo']} | {doc['paginas']} pág.")

    print("\n[6] Resumo do documento:")
    resumo = buscar_resumo(doc_id)
    print(f"     {resumo['resumo_gerado']}")

    print("\n[7] Perguntas do documento:")
    for p in listar_perguntas(doc_id):
        print(f"     P: {p['pergunta']}")
        print(f"     R: {p['resposta']}")

    print("\n" + "=" * 50)
    print("  Banco de dados funcionando corretamente!")
    print("=" * 50)