"""Testes do banco — são pulados automaticamente se o PostgreSQL não estiver disponível."""
import uuid
import pytest

try:
    from database import database as db
    db.criar_tabelas()
    BANCO_OK = True
except Exception:
    BANCO_OK = False

pytestmark = pytest.mark.skipif(not BANCO_OK, reason="PostgreSQL indisponível")


@pytest.fixture
def documento():
    marca = uuid.uuid4().hex[:8]
    doc_id = db.inserir_documento(f"teste_{marca}.pdf", "/tmp/x.pdf", "texto do teste", 2)
    yield doc_id, marca
    with db.conectar() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documentos WHERE id = %s;", (doc_id,))  # apaga em cascata


def test_conversa_completa(documento):
    doc_id, marca = documento
    conversa = db.criar_conversa(doc_id, f"Pergunta {marca}", "perguntas", "Detalhado")
    db.inserir_mensagem(conversa, "usuario", "Qual o valor?", "Detalhado")
    db.inserir_mensagem(conversa, "ia", "R$ 15.000,00", "Detalhado", "Claude")

    msgs = db.listar_mensagens(conversa)
    assert [m["papel"] for m in msgs] == ["usuario", "ia"]
    assert msgs[1]["api"] == "Claude"

    lista = db.listar_conversas(busca=marca)
    assert [c["id"] for c in lista] == [conversa]
    assert lista[0]["total_mensagens"] == 2 and lista[0]["nome_arquivo"].startswith("teste_")


def test_busca_no_conteudo_das_mensagens_e_filtro_por_tipo(documento):
    doc_id, marca = documento
    conversa = db.criar_conversa(doc_id, "Sem a marca no título", "perguntas", "Estudo")
    db.inserir_mensagem(conversa, "ia", f"resposta com {marca}")
    resumo = db.criar_conversa(doc_id, "Resumo", "resumo", "Resumido")
    db.inserir_mensagem(resumo, "ia", "resumo qualquer")

    assert conversa in [c["id"] for c in db.listar_conversas(busca=marca)]
    ids_resumo = [c["id"] for c in db.listar_conversas(tipo="resumo")]
    assert resumo in ids_resumo and conversa not in ids_resumo


def test_busca_trata_percentual_e_underscore_como_texto_literal(documento):
    doc_id, marca = documento
    conversa = db.criar_conversa(doc_id, f"multa de 5% {marca}", "perguntas")
    db.inserir_mensagem(conversa, "usuario", "x")
    assert conversa in [c["id"] for c in db.listar_conversas(busca="5% " + marca)]
    assert db.listar_conversas(busca="%%%_nao_existe_" + marca) == []


def test_renomear_excluir_e_cascata(documento):
    doc_id, marca = documento
    conversa = db.criar_conversa(doc_id, "Antigo", "perguntas")
    db.inserir_mensagem(conversa, "usuario", "oi")
    db.renomear_conversa(conversa, f"Novo {marca}")
    assert db.buscar_conversa(conversa)["titulo"] == f"Novo {marca}"

    db.excluir_conversa(conversa)
    assert db.buscar_conversa(conversa) is None
    assert db.listar_mensagens(conversa) == []
    assert db.buscar_documento(doc_id) is not None      # o documento permanece


def test_buscar_documento(documento):
    doc_id, _ = documento
    doc = db.buscar_documento(doc_id)
    assert doc["texto_extraido"] == "texto do teste" and doc["paginas"] == 2
