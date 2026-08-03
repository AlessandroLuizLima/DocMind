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