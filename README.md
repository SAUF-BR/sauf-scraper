# sauf-scraper

Motor de extração de dados de cursos do SAUF-BR. Coleta dos sites das universidades
e envia um lote por instituição para a API Java (`POST /api/v1/ingestao/lotes`).

Os dados das instituições vêm do Censo da Educação Superior (INEP), importados só para as
instituições que têm spider. O site de cada instituição é a fonte principal dos cursos:
o scraper envia todos os cursos que encontrar, com o link da página de cada um. O Censo
completa o que o site não mostra e liga o curso ao código e-MEC, quando ele existe.
Detalhes em [docs/MAPEAMENTO_CENSO.md](docs/MAPEAMENTO_CENSO.md).

## Rodando (Windows / PowerShell)

```powershell
# 1. Instalar o uv (uma vez só)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Na pasta do projeto
cd E:\repositories\sauf-scraper
uv sync                     # cria a .venv com as versões exatas do uv.lock
copy .env.example .env      # ajuste os valores

# 3. Comandos do dia a dia
uv run sauf-scraper --listar          # spiders registrados
uv run sauf-scraper --dry-run         # coleta e grava em output/*.json (não precisa do backend)
uv run sauf-scraper --ies uem --mostrar   # coleta só uma instituição e mostra na tela
uv run sauf-scraper --ies uem         # coleta só uma instituição e envia para a API
uv run sauf-scraper censo --mostrar   # lê o Censo (INEP) das IES com spider e mostra na tela
uv run sauf-scraper censo             # envia instituições e ofertas do Censo para a API
uv run sauf-scraper casar --ies uem   # gera a tabela site -> código e-MEC (depois do --dry-run)
uv run pytest                         # testes
uv run ruff check . ; uv run ruff format .   # lint e formatação
```

O código de saída é `1` se qualquer instituição falhar (o Jenkins/cron marca como falha),
mas as outras continuam sendo processadas.

## Estrutura

Explicação detalhada de cada arquivo: [docs/ESTRUTURA.md](docs/ESTRUTURA.md).

```
src/sauf_scraper/
├── cli.py               # argumentos de linha de comando
├── core/
│   ├── config.py        # variáveis SAUF_* (.env)
│   ├── models.py        # formato do lote (Pydantic) = contrato com a API Java
│   ├── pipeline.py      # roda os spiders isolados e envia cada lote
│   └── logging.py       # log em JSON, uma linha por evento
├── client/
│   ├── http.py          # GET "educado": User-Agent, robots.txt e delay por domínio
│   └── destinos.py      # ApiSauf (POST) e ArquivoJson (--dry-run)
├── spiders/             # um arquivo por instituição (herda de Spider)
└── parsers/             # HTML/JSON bruto -> dados (isolado do request)
tests/                   # pytest; HTML "congelado" de cada IES vai em tests/fixtures/
```

## Como adicionar uma instituição

1. Crie `src/sauf_scraper/spiders/<chave>.py` com uma classe que herda de `Spider`,
   define `chave = "<chave>"` e `codigo_emec = <código da IES no e-MEC>` e implementa `coletar()` devolvendo um `LoteIngestao`.
2. Coloque a lógica de parsing em `src/sauf_scraper/parsers/<chave>.py`.
3. Registre a classe em `src/sauf_scraper/spiders/__init__.py`.
4. Salve um HTML real em `tests/fixtures/<chave>/` e escreva um teste do parser com ele.
