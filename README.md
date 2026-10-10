# sauf-scraper

Motor de extração de dados de cursos do SAUF-BR. Coleta dos sites das universidades
e envia um lote por instituição para a API Java (`POST /api/v1/ingestao/lotes`).

Os dados das instituições vêm do Censo da Educação Superior (INEP), importados só para as
instituições que têm spider. O site de cada instituição é a fonte principal dos cursos:
o scraper envia todos os cursos que encontrar, com o link da página de cada um. O Censo
completa o que o site não mostra e liga o curso ao código e-MEC, quando ele existe.
Detalhes em [docs/MAPEAMENTO_CENSO.md](docs/MAPEAMENTO_CENSO.md).

Vai colaborar? Leia o [CONTRIBUTING.md](CONTRIBUTING.md) (como funciona, setup, como criar
um spider, testes e regras do time) e o [docs/CHECKLIST_SCRAPERS.md](docs/CHECKLIST_SCRAPERS.md)
(scrapers que já existem e os que faltam).

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

## Como popular a API

### Pré-requisitos

1. A API (`sauf-api`) rodando: `mvn spring-boot:run` na pasta dela.
2. No `.env` deste projeto:
   - `SAUF_API_BASE_URL=http://localhost:8080` (sem `/api/v1` no fim);
   - `SAUF_API_KEY` com **o mesmo valor** do `SAUF_API_KEY` do `.env` da API.
3. Os microdados do Censo (INEP) na pasta `microdados_censo_da_educacao_superior_2024/`,
   dentro deste projeto (já está no `.gitignore`). Para usar outra pasta, defina
   `SAUF_CENSO_DIR` no `.env` ou passe `--pasta` no comando.

### Exemplo: do zero até ver os cursos da UEM na API

> As saídas abaixo são **ilustrativas**: horários, ids, contagens e textos mudam a cada
> execução. O que importa é o formato e as mensagens.

**Passo 1. Subir a API** (terminal 1, na pasta `sauf-api`):

```powershell
mvn spring-boot:run
```

Espere estas linhas no log (na primeira vez o Flyway cria as tabelas):

```
... o.f.core.internal.command.DbMigrate : Successfully applied 2 migrations to schema "public", now at version v2
... o.s.boot.tomcat.TomcatWebServer      : Tomcat started on port 8080 (http) with context path '/'
... b.com.sauf_api.SaufApiApplication    : Started SaufApiApplication in 6.8 seconds
```

Deixe esse terminal aberto. Nas próximas vezes aparece `Schema "public" is up to date`.

**Passo 2. Importar o Censo** (terminal 2, na pasta `sauf-scraper`):

```powershell
uv run sauf-scraper censo
```

```json
{"ts": "2026-10-09T18:30:02+00:00", "level": "INFO", "logger": "sauf_scraper", "msg": "censo lido", "ano": 2024, "instituicoes": 1, "ofertas": 93}
{"ts": "2026-10-09T18:30:03+00:00", "level": "INFO", "logger": "sauf_scraper", "msg": "censo enviado", "resposta": {"criados": 93, "atualizados": 0, "inalterados": 0, "inativados": 0, "rejeitados": []}}
```

- `censo lido`: achou no Censo 2024 a instituição de cada spider registrado (hoje só a UEM,
  e-MEC 57) e os cursos dela.
- `censo enviado`: a API cadastrou a instituição e guardou os cursos do Censo como
  complemento. Eles ainda **não aparecem** no catálogo: só os cursos do site aparecem (D-33).
- Rodando de novo, os números passam para `atualizados`/`inalterados`; isso é normal.

**Passo 3. Coletar e enviar a UEM** (terminal 2; leva alguns minutos por causa do intervalo
de 2 s entre as páginas):

```powershell
uv run sauf-scraper --ies uem
```

```json
{"ts": "2026-10-09T18:36:41+00:00", "level": "INFO", "logger": "sauf_scraper.core.pipeline", "msg": "spider ok", "spider": "uem", "cursos": 67, "resposta": {"criados": 67, "atualizados": 0, "inalterados": 0, "inativados": 0, "rejeitados": []}}
{"ts": "2026-10-09T18:36:41+00:00", "level": "INFO", "logger": "sauf_scraper", "msg": "execução finalizada", "execucaoId": "20261009T183205Z", "resultados": [{"chave": "uem", "sucesso": true, "cursos": 67, "erro": null, "segundos": 276.4}]}
```

`"sucesso": true` e `rejeitados` vazio = tudo entrou. Se algum curso for recusado, a chave
dele aparece em `rejeitados`.

**Passo 4. Conferir na API** (navegador ou Swagger em http://localhost:8080/api/v1/swagger):

http://localhost:8080/api/v1/cursos?busca=software devolve o catálogo (curso genérico):

```json
{
  "content": [
    {
      "id": "3f6c2a7e-...",
      "nome": "Engenharia de Software",
      "area": {"id": "9b1d...", "nome": "Computação e Tecnologias da Informação e Comunicação (TIC)"},
      "imagemUrl": null,
      "totalUniversidades": 1,
      "modalidades": ["presencial"],
      "graus": ["bacharelado"],
      "duracaoSemestresMin": 10,
      "duracaoSemestresMax": 10,
      "notaCorteSisuMin": null
    }
  ],
  "page": 0, "size": 12, "totalElements": 1, "totalPages": 1
}
```

Com o `id` do curso, http://localhost:8080/api/v1/cursos/{id}/ofertas mostra a oferta da UEM,
com o `sobre` e o `mercadoTrabalho`:

```json
{
  "content": [
    {
      "nomeNoSite": "Engenharia de Software",
      "universidade": {"nome": "Universidade Estadual de Maringá", "sigla": "UEM", "tipo": "publica"},
      "opcoes": [{"grau": "bacharelado", "turno": "Noturno"}],
      "modalidade": "presencial",
      "sobre": "O objetivo principal do curso de Bacharelado em Engenharia de Software da UEM é formar profissionais...",
      "mercadoTrabalho": "O curso de graduação em Engenharia de Software forma profissionais altamente capacitados...",
      "duracaoSemestres": 10,
      "cidade": "Maringá", "uf": "PR",
      "vagas": 40, "gratuito": true,
      "urlOrigem": "https://www.pen.uem.br/site/public/curso/...",
      "notaCorteSisu": null, "mensalidade": null
    }
  ],
  "page": 0, "size": 20, "totalElements": 1, "totalPages": 1
}
```

(Resposta resumida: alguns campos foram omitidos. `null` em nota de corte e mensalidade é
esperado; ainda não há fonte para esses dados.)

Também vale abrir http://localhost:8080/api/v1/universidades (a UEM com o total de cursos)
e http://localhost:8080/api/v1/areas (o `totalCursos` de cada área sobe).

Para ver o que seria enviado **sem mandar nada** para a API, troque os passos 2 e 3 por
`uv run sauf-scraper censo --dry-run` e `uv run sauf-scraper --ies uem --dry-run`: eles gravam
`output/censo-2024.json` e `output/emec-57.json`.

### Quando rodar de novo

- `censo`: só com banco novo, Censo novo ou spider novo registrado. A coleta depende dele,
  porque a API só aceita cursos de instituições já cadastradas.
- `--ies uem`: quantas vezes quiser. Cada envio atualiza as ofertas; as que sumiram do site
  ficam inativas (não são apagadas).

### Deu erro?

| Mensagem | Causa | Solução |
|---|---|---|
| `422` "Instituição com código e-MEC 57 não está cadastrada. Rode o import do Censo antes." | A coleta (`--ies uem`) rodou antes do `censo`. | Rodar `uv run sauf-scraper censo` (passo 2) e depois a coleta de novo. |
| `401` | `SAUF_API_KEY` diferente nos dois `.env`. | Deixar os dois valores iguais e reiniciar a API. |
| `Connection refused` / `ConnectError` | A API não está no ar ou o `SAUF_API_BASE_URL` está errado. | Subir a API (passo 1) e conferir a URL (`http://localhost:8080`, sem `/api/v1`). |
| Arquivo do Censo não encontrado | Microdados fora da pasta esperada. | Ajustar `SAUF_CENSO_DIR` ou usar `--pasta`. |

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
