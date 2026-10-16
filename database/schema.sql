CREATE TABLE IF NOT EXISTS documentos (
    id             SERIAL PRIMARY KEY,
    nome_arquivo   VARCHAR(255) NOT NULL,
    caminho        TEXT,
    texto_extraido TEXT,
    paginas        INT,
    data_upload    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resumos (
    id             SERIAL PRIMARY KEY,
    documento_id   INT NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    resumo_gerado  TEXT NOT NULL,
    tokens_entrada INT,
    tokens_saida   INT,
    data_geracao   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS perguntas (
    id             SERIAL PRIMARY KEY,
    documento_id   INT NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    pergunta       TEXT NOT NULL,
    resposta       TEXT NOT NULL,
    tokens_entrada INT,
    tokens_saida   INT,
    data_pergunta  TIMESTAMP DEFAULT NOW()
);

-- ── Histórico de conversas e resumos (aba "Histórico") ────────
CREATE TABLE IF NOT EXISTS conversas (
    id               SERIAL PRIMARY KEY,
    documento_id     INT NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    titulo           VARCHAR(200) NOT NULL,
    tipo             VARCHAR(20) NOT NULL DEFAULT 'perguntas'
                     CHECK (tipo IN ('perguntas', 'resumo')),
    modo             VARCHAR(50),
    data_criacao     TIMESTAMP DEFAULT NOW(),
    data_atualizacao TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mensagens (
    id          SERIAL PRIMARY KEY,
    conversa_id INT NOT NULL REFERENCES conversas(id) ON DELETE CASCADE,
    papel       VARCHAR(10) NOT NULL CHECK (papel IN ('usuario', 'ia')),
    conteudo    TEXT NOT NULL,
    modo        VARCHAR(50),
    api         VARCHAR(100),
    data_envio  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversas_atualizacao ON conversas (data_atualizacao DESC);
CREATE INDEX IF NOT EXISTS idx_mensagens_conversa    ON mensagens (conversa_id);
