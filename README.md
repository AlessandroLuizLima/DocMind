# DocMind

Assistente inteligente de documentos PDF com apoio de Inteligência Artificial.

## Integrantes do Grupo

- Alessandro Luiz de Lima
- Douglas de Jesus
- Arthur Henrique Svidzinski
- Breno Suski

## Resumo da Automação Proposta

O DocMind é uma aplicação desktop (Python/Tkinter) que automatiza a análise de documentos em PDF por meio de Inteligência Artificial. O sistema permite que o usuário carregue um arquivo PDF e obtenha, de forma automática:

- Resumos do conteúdo do documento;
- Respostas a perguntas feitas sobre o conteúdo (modo Q&A);
- Extração de pontos-chave e insights;
- Conversão de trechos em áudio (texto-para-voz).

A proposta central da automação é eliminar a leitura manual e exaustiva de documentos extensos, delegando à IA (via API da Claude e da Gemini, orquestradas com LangChain) a tarefa de interpretar o conteúdo e responder de forma contextualizada, mantendo o histórico de interações persistido em banco de dados PostgreSQL. O projeto também incorpora validações de segurança (proteção contra prompt injection e sanitização de entradas) centralizadas em um pacote compartilhado (`docmind/`), garantindo que a automação seja executada de forma confiável e segura.

## Tecnologias e Ferramentas Utilizadas

**Linguagem e Interface**
- Python 3
- Tkinter (interface gráfica desktop, modo escuro)

**Inteligência Artificial**
- API Claude (Anthropic)
- API Gemini (Google)
- LangChain (orquestração dos modelos de IA)

**Processamento de Documentos**
- PyPDF2 (extração de texto de PDFs)
- gTTS (conversão de texto em áudio)

**Persistência de Dados**
- PostgreSQL
- psycopg2

**Qualidade e Segurança**
- Pytest (suíte de testes automatizados)
- GitHub Actions (CI/CD)
- Módulo de validação de segurança centralizado (`docmind/`)

**Controle de Versão**
- Git / GitHub

## Funcionalidades

**Modos da IA** (cada modo muda o tipo de saída, tanto no resumo quanto nas perguntas):

- **Extração de Dados**: lista datas, valores, nomes, prazos, definições e referências.
- **Resumido**: respostas curtas e resumo enxuto que cobre o documento inteiro.
- **Estudo**: explica como um professor e gera flashcards e questões de revisão com gabarito.
- **Detalhado**: resposta e resumo aprofundados, seção por seção.
- **Revisão Crítica**: aponta lacunas, ambiguidades, contradições e riscos.

**Resumos completos**: documentos longos são divididos em partes, cada parte é resumida e depois os resumos são unificados.

**Exemplo prático**: toda resposta da aba Perguntas termina com um exemplo (pode ser desligado na barra lateral). As perguntas consideram as mensagens anteriores da conversa.

**Histórico**: todas as conversas e resumos ficam salvos no PostgreSQL. Na aba Histórico é possível buscar, filtrar, abrir e continuar uma conversa, renomear e excluir.

## Instruções de Instalação, Dependências e Execução

### Pré-requisitos

- Python 3.10 ou superior instalado
- PostgreSQL instalado e em execução
- Chaves de API válidas para Claude (Anthropic) e/ou Gemini (Google)

### 1. Clonar o repositório

```bash
git clone https://github.com/AlessandroLuizLima/DocMind.git
cd DocMind
```

### 2. Criar e ativar um ambiente virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto com as seguintes chaves:

```
ANTHROPIC_API_KEY=sua_chave_aqui
GOOGLE_API_KEY=sua_chave_aqui
DB_HOST=localhost
DB_PORT=5432
DB_NAME=docmind
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
```

Os nomes `CLAUDE_API_KEY` e `GEMINI_API_KEY` também são aceitos. Se a chave do Google não for informada, todas as perguntas são respondidas pelo Claude.

### 5. Configurar o banco de dados

Crie o banco de dados PostgreSQL indicado no `.env`. As tabelas necessárias são criadas automaticamente na primeira execução da aplicação.

### 6. Executar a aplicação

```bash
python main.py
```

### 7. Executar os testes (opcional)

```bash
pytest
```

## Status Atual do Projeto

- [x] Interface gráfica funcional (Tkinter, modo escuro)
- [x] Integração com APIs de IA (Claude e Gemini via LangChain)
- [x] Persistência em PostgreSQL
- [x] Módulo de segurança centralizado com validação de entradas
- [x] Suíte de testes automatizados (Pytest) e pipeline de CI/CD (GitHub Actions)
- [ ] Deploy/distribuição final