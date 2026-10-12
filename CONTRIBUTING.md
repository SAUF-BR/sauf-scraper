# Como contribuir com o sauf-scraper

Guia para criar ou manter um scraper do SAUF-BR. Setup e comandos do dia a dia estão no
[README](README.md); detalhes arquivo por arquivo em [docs/ESTRUTURA.md](docs/ESTRUTURA.md);
Censo × site em [docs/MAPEAMENTO_CENSO.md](docs/MAPEAMENTO_CENSO.md); o que existe e o que
falta em [docs/CHECKLIST_SCRAPERS.md](docs/CHECKLIST_SCRAPERS.md). Decisões (D-xx):
`sauf-api/docs/DECISOES.md`.

## 1. Como funciona

O spider coleta os cursos do site de uma IES e envia **um lote por instituição** para a API.
Os dados da instituição e o complemento dos cursos (área, vagas, gratuidade) vêm do **Censo
(INEP)**, num fluxo separado (`sauf-scraper censo`).

| Pasta (`src/sauf_scraper/`) | Responsabilidade |
|---|---|
| `core/` | `config.py` (variáveis `SAUF_*`), `models.py` (contrato com a API), `pipeline.py` (roda cada spider isolado), `logging.py`. |
| `client/` | `http.py` (`HttpEducado`: robots.txt, User-Agent, delay) e `destinos.py` (tela, JSON ou API). |
| `parsers/` | Um arquivo por IES. Funções puras: HTML → dados, sem requisição. |
| `spiders/` | Um arquivo por IES: baixa as páginas, chama o parser e monta o `LoteIngestao`. `spiders/dados/` guarda os CSVs de casamento. |
| `censo/` | Leitura dos microdados e casamento site → código e-MEC. |

Fluxo: site → `HttpEducado` → parser → spider (+ códigos e-MEC do CSV) → `--mostrar` (tela),
`--dry-run` (`output/emec-<código>.json`) ou API (`POST /api/v1/ingestao/lotes`).

**Modelos Pydantic** (`core/models.py`): campos em `snake_case` no Python e **camelCase** no
JSON (`url_origem` → `urlOrigem`). Campo desconhecido é erro, enums são minúsculos (D-30) e
dado inválido falha **antes** do envio (log `spider gerou dado inválido`).

**`.env`:** prefixo `SAUF_` (ex.: `SAUF_API_BASE_URL`, `SAUF_API_KEY=<mesma chave da API>`).
Rode tudo **de dentro da pasta `sauf-scraper`**. Nunca commite nem compartilhe chaves.

## 2. Spider novo, passo a passo

Modelo: `parsers/uem.py`, `spiders/uem.py` e `tests/test_parser_uem.py`. No exemplo, a IES
fictícia tem chave `xyz` e código e-MEC `1234`.

1. **Levantamento:** código e-MEC da IES (cadastro e-MEC ou `CO_IES` do Censo), `robots.txt`
   e se as páginas são HTML simples. Salve a lista de cursos e 2 ou 3 páginas de curso como
   fixtures (seção 4).
2. **Parser** (`parsers/xyz.py`): funções puras como `extrair_lista` e `extrair_detalhes`.
   `None` quando o campo não aparece; textos longos sem HTML, com `\n` entre linhas e `\n\n`
   entre parágrafos (D-37); nada de dados pessoais.
3. **Spider** (`spiders/xyz.py`):

   ```python
   class XyzSpider(Spider):
       chave = "xyz"
       codigo_emec = 1234

       def coletar(self) -> LoteIngestao:
           codigos = codigos_confirmados(self.chave)
           cursos = []
           for item in extrair_lista(self.http.get(URL_LISTA).text):
               detalhes = extrair_detalhes(self.http.get(item.url).text)
               curso = Curso(
                   chave=montar_chave_curso("xyz", item.nome, item.cidade, detalhes.turno or ""),
                   url_origem=item.url,
                   nome=item.nome,  # + demais campos da tabela abaixo
               )
               cursos.append(aplicar_codigos(curso, codigos.get(curso.chave, [])))
           return LoteIngestao(
               execucao_id=self.execucao_id,
               fonte=Fonte(url=URL_LISTA),
               codigo_emec_instituicao=self.codigo_emec,
               cursos=cursos,
           )
   ```

   - Sempre `self.http.get`, nunca `requests` direto.
   - Chave sempre com `montar_chave_curso`: estável entre coletas e única no lote, senão a
     API duplica cursos.
   - **Uma página = um curso** (D-34): graus e turnos da página vão em `opcoes`.
4. **Registro:** adicione `XyzSpider.chave: XyzSpider` ao `SPIDERS` em `spiders/__init__.py`
   e confira com `uv run sauf-scraper --listar`. Isso libera o `--ies xyz` e inclui a IES no
   `censo`; rode o `censo` de novo para a API conhecer a instituição.
5. **Casamento com o e-MEC:**

   ```powershell
   uv run sauf-scraper --ies xyz --dry-run   # grava output/emec-1234.json
   uv run sauf-scraper casar --ies xyz       # gera/atualiza spiders/dados/xyz_codigos.csv
   ```

   Revise o CSV (abre no Excel). O spider só usa linhas com `confirmado = sim`:
   `direto` já vem confirmado; em `ambiguo`, confirme as linhas certas; em `sem_par`,
   preencha o código à mão se achar. Rodar `casar` de novo preserva o que foi confirmado.
   O CSV **vai para o Git**. Regras: [MAPEAMENTO_CENSO.md](docs/MAPEAMENTO_CENSO.md).
6. Confira a [definição de pronto](docs/CHECKLIST_SCRAPERS.md#4-definição-de-pronto-spider-novo).

### Campos do curso (`Curso`)

| Campo (JSON) | Obrigatório? | Observação |
|---|---|---|
| `chave` | **sim** | `montar_chave_curso(...)`; só `a-z`, `0-9`, `-` e `:`. |
| `urlOrigem` | **sim** | URL da página do curso: crédito e link "acessar o site". |
| `nome` | **sim** | Como aparece no site. |
| `opcoes` | não | Lista de `{grau, turno}`. |
| `modalidade` | não | `presencial`, `semipresencial` ou `ead`. |
| `turno` | não | Texto do site, ex.: `"Matutino ou Noturno"`. |
| `sobre` | não | Texto "Sobre o curso". |
| `mercadoTrabalho` | não | "Mercado de trabalho" ou "Campo de atuação" (D-46, D-47). |
| `duracaoTexto` / `duracaoSemestres` | não | Texto original e inteiro > 0 (`semestres_de_texto`). |
| `cidade` / `uf` | não | `uf` com duas letras maiúsculas. |
| `codigosEmec` | não | **Não preencha à mão**: vem do CSV via `aplicar_codigos` (D-35). |

No `LoteIngestao` tudo é obrigatório: `execucaoId`, `fonte`, `codigoEmecInstituicao` e
`cursos`. "Não obrigatório" só quer dizer que a validação aceita `null`; o que uma IES precisa
para contar como **completa** está no [checklist](docs/CHECKLIST_SCRAPERS.md#12-scraper-de-mais-4-universidades-a-definir-).

## 3. Enviando os dados

```powershell
uv run sauf-scraper --ies xyz --mostrar   # tela
uv run sauf-scraper --ies xyz --dry-run   # output/emec-<código>.json (sem API)
uv run sauf-scraper censo                 # API: 1º o Censo (com a API no ar)
uv run sauf-scraper --ies xyz             # API: 2º o spider
```

`SAUF_API_BASE_URL` sem `/api/v1`. Exemplo completo e erros comuns (422, 401, conexão
recusada): ["Como popular a API" no README](README.md#como-popular-a-api).

## 4. Testes e qualidade

```powershell
uv run pytest
uv run ruff check . ; uv run ruff format .
```

- Nenhum teste acessa a internet: parsers usam HTML salvo e HTTP/API usam `responses`.
- **Fixtures** em `tests/fixtures/<chave>/` ficam fora do Git (`.gitignore`): são páginas de
  terceiros e podem ter dados pessoais. Para gerar: salve a página uma vez ("Salvar como →
  somente HTML"), troque nomes e e-mails por fictícios ("Fulano de Tal") e leia com
  `ler("<nome>.html")`. Regressões curtas podem usar um trecho de HTML no próprio teste.
- Antes de commitar: `pytest` e `ruff` sem erros.

## 5. Regras do time

1. **Commit:** `TR-<n> Descrição` (card do Jira); branch `TR-<n>-Descricao`. Não commite
   `.env`, `output/`, microdados nem `tests/fixtures/`.
2. **LGPD:** nada de nomes, e-mails ou telefones de pessoas. A seção "Coordenação" fica de fora.
3. **Site antes do Censo** (D-33): o site é a fonte principal; o Censo (2024) só complementa
   e não cria cursos.
4. **`urlOrigem` sempre preenchido:** crédito à fonte e link oficial para o estudante.
5. **Educação com os servidores:** só `self.http.get` (robots.txt + delay de 2 s), só as
   páginas necessárias, sem coletas repetidas à toa; para investigar, 1 ou 2 páginas.
6. **Regra nova de negócio** é combinada com o time e registrada no `DECISOES.md`.
