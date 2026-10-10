# Como contribuir com o sauf-scraper

Guia para quem vai criar ou manter um scraper do SAUF-BR. Leia junto com:

- [README.md](README.md): comandos do dia a dia e a seção **"Como popular a API"**;
- [docs/ESTRUTURA.md](docs/ESTRUTURA.md): explicação arquivo por arquivo (com glossário Python → Java/TS);
- [docs/MAPEAMENTO_CENSO.md](docs/MAPEAMENTO_CENSO.md): o que vem do Censo e o que vem do site;
- [docs/CHECKLIST_SCRAPERS.md](docs/CHECKLIST_SCRAPERS.md): o que já existe e o que falta;
- `sauf-api/docs/DECISOES.md`: as decisões do projeto (D-xx) citadas aqui.

---

## 1. Como o projeto funciona

O scraper coleta os **cursos de graduação** do site de cada instituição (IES) e envia um
**lote por instituição** para a API Java. Os dados da instituição em si (nome, tipo, UF) e o
complemento de cada curso (área, vagas, gratuidade) vêm do **Censo da Educação Superior
(INEP)**, num fluxo separado.

### Pastas (`src/sauf_scraper/`)

| Pasta | Responsabilidade |
|---|---|
| `cli.py` | Ponto de entrada: `sauf-scraper`, `sauf-scraper censo` e `sauf-scraper casar`. |
| `core/` | Núcleo, sem nada específico de um site: `config.py` (variáveis `SAUF_*`), `models.py` (contrato do lote com a API), `pipeline.py` (roda os spiders isolados), `logging.py` (log em JSON). |
| `client/` | Conversa com o mundo externo: `http.py` (`HttpEducado`: robots.txt, User-Agent e delay) e `destinos.py` (`Terminal` para `--mostrar`, `ArquivoJson` para `--dry-run`, `ApiSauf` para a API). |
| `parsers/` | Um arquivo por IES. **Funções puras**: recebem HTML (texto) e devolvem dados. Não fazem requisição. |
| `spiders/` | Um arquivo por IES. Decide quais páginas baixar, chama o parser e monta o `LoteIngestao`. `spiders/dados/` guarda as tabelas de casamento (`<chave>_codigos.csv`). |
| `censo/` | Leitura dos microdados do Censo (`leitor.py`, `modelos.py`) e a tabela de casamento site → código e-MEC (`casamento.py`). |

### Fluxo de dados

```
Site da IES ──HttpEducado──> parser (HTML → dados) ──> spider (monta Curso/LoteIngestao)
                                                          │  + códigos e-MEC confirmados
                                                          │    (spiders/dados/<chave>_codigos.csv)
                                                          ▼
                                     --mostrar → tela | --dry-run → output/emec-<código>.json
                                                          | (padrão) → POST /api/v1/ingestao/lotes

Microdados do Censo (CSV) ──censo/leitor──> LoteCenso (só IES com spider registrado)
                                     --mostrar → tela | --dry-run → output/censo-<ano>.json
                                                          | (padrão) → POST /api/v1/ingestao/censo
```

O pipeline roda cada spider **isolado**: se um quebra, os outros continuam, e o código de
saída vira `1`.

### Modelos (Pydantic)

Os modelos de `core/models.py` são o **contrato com a API**. No Python os campos são
`snake_case`; no JSON saem em **camelCase** (`url_origem` → `urlOrigem`,
`mercado_trabalho` → `mercadoTrabalho`) por causa do `alias_generator=to_camel` do
`SaufModel`. A validação é rígida:

- campo desconhecido gera erro (`extra="forbid"`);
- enums em minúsculas: `Modalidade` = `presencial | semipresencial | ead`,
  `Grau` = `bacharelado | licenciatura | tecnologo | bacharelado_e_licenciatura` (D-30);
- espaços nas pontas dos textos são removidos.

Se o site mudar e o spider gerar dado inválido, a validação falha **antes** de enviar, e o
log mostra `spider gerou dado inválido`.

---

## 2. Setup

Requisitos: Python 3.12+ (o `uv` instala) e Git.

```powershell
# 1. Instalar o uv (uma vez só)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Na pasta do projeto
cd E:\repositories\sauf-scraper     # ou onde você clonou
uv sync
copy .env.example .env
```

O `.env` usa o prefixo `SAUF_` (cada campo de `core/config.py` vira `SAUF_<CAMPO>`). Exemplo
**só com placeholders**:

```dotenv
SAUF_API_BASE_URL=http://localhost:8080
SAUF_API_KEY=<mesmo valor do SAUF_API_KEY do .env da API>
SAUF_REQUEST_DELAY_SECONDS=2
# Opcional: pasta dos microdados do Censo (padrão: microdados_censo_da_educacao_superior_2024)
# SAUF_CENSO_DIR=microdados_censo_da_educacao_superior_2024
```

- **Rode os comandos de dentro da pasta `sauf-scraper`.** O `.env`, a pasta `output/` e a
  pasta dos microdados são procurados a partir da pasta atual.
- O `.env` nunca vai para o Git. Não cole chaves nem senhas em issues, commits ou chats.
- Os microdados do Censo (`microdados_censo_da_educacao_superior_2024/`) também ficam fora
  do Git: baixe o .zip no site do INEP e extraia na raiz do projeto.

---

## 3. Criando um spider novo (passo a passo)

Use o spider da UEM como modelo: `parsers/uem.py`, `spiders/uem.py` e
`tests/test_parser_uem.py`. Nos exemplos, a IES fictícia tem chave `xyz` e código e-MEC `1234`.

### 3.1. Antes de codar

1. Descubra o **código e-MEC da instituição** (no cadastro e-MEC ou na coluna `CO_IES` dos
   microdados do Censo). Ex.: UEM = 57.
2. Confira o `robots.txt` do site e se as páginas de curso são HTML simples (sem login, sem
   CAPTCHA). Se o conteúdo só aparece via JavaScript, procure a API/JSON que a página usa.
3. Salve no seu computador algumas páginas reais para os testes (seção 5): a lista de cursos
   e 2 ou 3 páginas de curso diferentes.

### 3.2. Parser: `src/sauf_scraper/parsers/xyz.py`

Funções puras que recebem o HTML e devolvem dados, como `extrair_lista` e
`extrair_detalhes` da UEM. Regras:

- não fazer requisição dentro do parser;
- devolver `None` quando o campo não aparece na página (não inventar valor);
- textos longos (`sobre`, `mercadoTrabalho`) em **texto puro**, sem HTML: `\n` entre linhas
  e `\n\n` entre parágrafos (D-37);
- **não coletar dados pessoais** (seção 7).

### 3.3. Spider: `src/sauf_scraper/spiders/xyz.py`

```python
from sauf_scraper.censo.casamento import aplicar_codigos, codigos_confirmados
from sauf_scraper.core.models import Curso, Fonte, LoteIngestao, montar_chave_curso
from sauf_scraper.parsers.xyz import extrair_detalhes, extrair_lista
from sauf_scraper.spiders.base import Spider

URL_LISTA = "https://www.xyz.edu.br/cursos"


class XyzSpider(Spider):
    chave = "xyz"  # usado no --ies xyz e no nome do CSV de casamento
    codigo_emec = 1234  # código e-MEC da instituição

    def coletar(self) -> LoteIngestao:
        lista = extrair_lista(self.http.get(URL_LISTA).text)
        codigos = codigos_confirmados(self.chave)
        cursos = []
        for item in lista:
            detalhes = extrair_detalhes(self.http.get(item.url).text)
            curso = Curso(
                chave=montar_chave_curso("xyz", item.nome, item.cidade, detalhes.turno or ""),
                url_origem=item.url,
                nome=item.nome,
                # ... demais campos (tabela abaixo)
            )
            cursos.append(aplicar_codigos(curso, codigos.get(curso.chave, [])))
        return LoteIngestao(
            execucao_id=self.execucao_id,
            fonte=Fonte(url=URL_LISTA),
            codigo_emec_instituicao=self.codigo_emec,
            cursos=cursos,
        )
```

- Use **sempre** `self.http.get` (nunca `requests` direto): ele respeita o robots.txt e o
  delay entre requisições.
- Gere a chave com `montar_chave_curso`. A mesma página precisa gerar sempre a mesma chave,
  senão a API cria cursos duplicados. A chave precisa ser única no lote (a UEM verifica
  chaves repetidas e falha se houver).
- **Uma página do site = um curso** (D-34). Se a página oferece mais de um grau ou turno,
  eles vão na lista `opcoes`, não em cursos separados.

### 3.4. Campos do curso (`Curso` em `core/models.py`)

| Campo (Python → JSON) | Obrigatório no modelo? | Observação |
|---|---|---|
| `chave` → `chave` | **sim** | `montar_chave_curso(...)`; só `a-z`, `0-9`, `-` e `:`. |
| `url_origem` → `urlOrigem` | **sim** | URL válida da página do curso. É o crédito à fonte e o link "acessar o site". |
| `nome` → `nome` | **sim** | Nome como aparece no site. |
| `opcoes` → `opcoes` | não (padrão `[]`) | Lista de `{grau, turno}`. Recomendado: o front mostra grau e turno. |
| `modalidade` → `modalidade` | não | `presencial`, `semipresencial` ou `ead`. |
| `turno` → `turno` | não | Texto do site, ex.: `"Matutino ou Noturno"`. |
| `sobre` → `sobre` | não | Texto "Sobre o curso", puro. |
| `mercado_trabalho` → `mercadoTrabalho` | não | "Mercado de trabalho" ou "Campo de atuação" (D-46, D-47). |
| `duracao_texto` → `duracaoTexto` | não | Texto original, ex.: `"5 anos"`. |
| `duracao_semestres` → `duracaoSemestres` | não | Inteiro > 0. Use `semestres_de_texto(...)`; fica `None` se o texto não for simples. |
| `cidade` → `cidade` | não | Cidade do campus. |
| `uf` → `uf` | não | Duas letras maiúsculas, ex.: `PR`. |
| `codigos_emec` → `codigosEmec` | não (padrão `[]`) | **Não preencha à mão**: vem da tabela de casamento via `aplicar_codigos`. Uso interno (D-35). |

No `LoteIngestao`, todos os campos são obrigatórios: `execucao_id` (use `self.execucao_id`),
`fonte` (`Fonte(url=...)` da página de lista), `codigo_emec_instituicao` (> 0) e `cursos`.

"Não obrigatório no modelo" quer dizer que a validação aceita `None`. Para a IES contar como
**completa** na apresentação, veja o que se espera em
[docs/CHECKLIST_SCRAPERS.md](docs/CHECKLIST_SCRAPERS.md).

### 3.5. Registrar o spider

Em `src/sauf_scraper/spiders/__init__.py`:

```python
from sauf_scraper.spiders.uem import UemSpider
from sauf_scraper.spiders.xyz import XyzSpider

SPIDERS: dict[str, type[Spider]] = {UemSpider.chave: UemSpider, XyzSpider.chave: XyzSpider}
```

Confira com `uv run sauf-scraper --listar`. O registro faz duas coisas:

- libera o `--ies xyz`;
- inclui a IES no import do Censo (`codigos_emec()` lê os spiders registrados). Por isso,
  depois de registrar, é preciso rodar o `censo` de novo para a API conhecer a instituição.

### 3.6. Casamento com os códigos e-MEC do Censo

O site não informa o código e-MEC de cada curso. A tabela
`src/sauf_scraper/spiders/dados/<chave>_codigos.csv` (UTF-8, separador `;`) faz essa ligação,
com **uma linha por par página × código**:

```powershell
uv run sauf-scraper --ies xyz --dry-run   # 1º: grava output/emec-1234.json
uv run sauf-scraper casar --ies xyz       # 2º: gera/atualiza spiders/dados/xyz_codigos.csv
```

Depois revise o CSV (dá para abrir no Excel):

| `status` | Significado | O que fazer |
|---|---|---|
| `direto` | um único candidato no Censo | já vem `confirmado = sim` |
| `ambiguo` | vários candidatos (veja `sugestao`) | trocar `confirmado` para `sim` nas linhas certas |
| `sem_par` | nenhum candidato | preencher `codigo_emec` à mão se achar o código, ou deixar `nao` |

- O spider só usa as linhas com `confirmado = sim`.
- Rodar `casar` de novo **preserva** as páginas que já têm linha confirmada à mão.
- O CSV **vai para o Git**: ele é revisado à mão e o spider depende dele.
- Detalhes das regras de casamento: [docs/MAPEAMENTO_CENSO.md](docs/MAPEAMENTO_CENSO.md#tabela-de-casamento-página-do-site--co_curso).

---

## 4. Enviando os dados

### Para a tela ou para um arquivo JSON (não precisa da API)

```powershell
uv run sauf-scraper --ies xyz --mostrar   # resumo de cada curso na tela
uv run sauf-scraper --ies xyz --dry-run   # grava output/emec-<código>.json
uv run sauf-scraper censo --dry-run       # grava output/censo-<ano>.json
```

Abra o `output/emec-<código>.json` e confira os campos da tabela 3.4. A pasta `output/` não
vai para o Git.

### Para a API

Ordem: **subir a API → `censo` → spider**.

```powershell
uv run sauf-scraper censo
uv run sauf-scraper --ies xyz
```

- `SAUF_API_BASE_URL` é a raiz do servidor, **sem `/api/v1`** (ex.: `http://localhost:8080`).
- `SAUF_API_KEY` igual ao `SAUF_API_KEY` do `.env` da API.

Exemplo completo, como conferir e erros comuns (422 de instituição não cadastrada, 401 de
chave diferente, conexão recusada): seção
[**"Como popular a API"** do README](README.md#como-popular-a-api).

---

## 5. Testes e qualidade

```powershell
uv run pytest                                  # testes
uv run ruff check . ; uv run ruff format .     # lint e formatação
```

- **Nenhum teste acessa a internet.** Parsers são testados com HTML salvo; HTTP e API com a
  biblioteca `responses`, que simula as respostas. Não faça coleta real dentro de teste.
- **Fixtures HTML** ficam em `tests/fixtures/<chave>/` e estão no `.gitignore`: são cópias de
  páginas de terceiros e podem conter dados pessoais (ex.: nome e e-mail da coordenação), então
  ficam só na sua máquina. Para gerar:
  1. abra a página no navegador e use "Salvar como → somente HTML" (ou baixe **uma vez** com
     `curl`), salvando em `tests/fixtures/<chave>/<nome>.html`;
  2. troque nomes e e-mails reais por dados fictícios (ex.: "Fulano de Tal",
     `coordenador@exemplo.br`);
  3. leia com o helper `ler("<nome>.html")`, como em `tests/test_parser_uem.py`.
- Testes curtos de regressão podem usar um **trecho** de HTML direto no código do teste,
  encurtado e sem dados pessoais (vários testes da UEM fazem isso).
- Antes de abrir PR ou commitar: `pytest` e `ruff` sem erros.

---

## 6. Commits e branches

- Mensagem de commit: `TR-<n> Descrição`, com o número do card no Jira. Ex.:
  `TR-260 Adição de campo 'mercadoTrabalho', entre outras melhorias`.
- Branch: o padrão em uso é `TR-<n>-Descricao` (ex.: `TR-260-Scraper-UEM`).
- Commits pequenos e com um assunto só. Não commite `.env`, `output/`, microdados do Censo
  nem `tests/fixtures/`.

---

## 7. Regras do time

1. **Nada de dados pessoais (LGPD).** Não colete nomes, e-mails ou telefones de pessoas. A
   seção "Coordenação" das páginas da UEM fica de fora de propósito; faça o mesmo nas outras IES.
2. **O site da IES é a fonte principal; o Censo só complementa** (D-33). O Censo mais recente
   é de 2024, e o site é atualizado pela própria universidade. Graus e turnos vêm da página; o
   Censo não cria cursos que não existem no site.
3. **Sempre preencha `urlOrigem`.** É o crédito à fonte e o link que o estudante usa para
   confirmar a informação no site oficial.
4. **Seja educado com os servidores.** Use só `self.http.get` (robots.txt + delay de
   `SAUF_REQUEST_DELAY_SECONDS`, padrão 2 s), baixe só as páginas necessárias e não rode
   coletas completas repetidas sem motivo. Para investigar um problema, baixe 1 ou 2 páginas.
5. **Regra nova vira decisão registrada.** Se o spider precisar de uma regra de negócio nova
   (ex.: o que conta como "mercado de trabalho"), combine com o time e registre no
   `sauf-api/docs/DECISOES.md`.
