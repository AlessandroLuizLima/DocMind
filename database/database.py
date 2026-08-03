import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host":     "127.0.0.1",
    "port":     5432,
    "dbname":   "docmind",
    "user":     "postgres",
    "password": "postgres"
}

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