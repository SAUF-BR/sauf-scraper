# Guia do esqueleto do sauf-scraper

Este guia explica para que serve cada arquivo, por que ele tem esse nome e quais conceitos
de Python aparecem nele. As comparações usam Spring Boot e TypeScript, que você já conhece.

---

## 1. Visão geral: o que acontece quando você roda `uv run sauf-scraper --dry-run`

```
cli.py            lê os argumentos (--dry-run, --ies) e monta as peças
  │
  ├─ config.py    lê as variáveis SAUF_* do .env  ──────────────► Settings
  ├─ http.py      cria o HttpEducado (GET com robots.txt e delay)
  ├─ destinos.py  escolhe o destino: ArquivoJson (dry-run) ou ApiSauf (POST)
  │
  └─ pipeline.py  para cada spider registrado em spiders/__init__.py:
                    1. spider.coletar()  → baixa páginas com o HttpEducado
                                          → usa um parser para extrair os dados
                                          → devolve um LoteIngestao (models.py)
                    2. destino.enviar(lote)
                    3. se der erro, registra e passa para o próximo spider
                  no fim: resumo no log e código de saída 0 (ok) ou 1 (houve falha)
```

Em Spring, seria algo assim: `cli.py` faz o papel do `main` com `CommandLineRunner`,
`pipeline.py` é um `@Service`, `destinos.py` é uma interface com duas implementações e
`models.py` são os DTOs.

---

## 2. Arquivos da raiz

| Arquivo | Para que serve | Equivalente que você conhece |
|---|---|---|
| `pyproject.toml` | Nome, versão, dependências e configuração das ferramentas (pytest, ruff) | `package.json` / `pom.xml` |
| `uv.lock` | Versões **exatas** de todas as dependências, inclusive as indiretas. Vai para o Git | `package-lock.json` |
| `.python-version` | Versão do Python do projeto (3.12). O `uv` baixa essa versão sozinho se você não tiver | `.nvmrc` |
| `.venv/` | Pasta criada pelo `uv sync` com as bibliotecas instaladas. **Não** vai para o Git | `node_modules/` |
| `.env.example` | Modelo das variáveis de ambiente. Você copia para `.env` (que não vai para o Git) | `.env.example` do Next |
| `.gitignore` | O que o Git ignora (`.venv`, `.env`, `output/`, caches) | igual |
| `README.md` | Como instalar e rodar | igual |

No `pyproject.toml`, três blocos merecem atenção:

- `dependencies`: bibliotecas que o scraper usa em produção (`requests`, `beautifulsoup4`,
  `pydantic`, `pydantic-settings`).
- `[dependency-groups] dev`: só para desenvolvimento (`pytest`, `responses`, `ruff`). É o
  `devDependencies` do npm.
- `[project.scripts]`: cria o comando `sauf-scraper` apontando para a função `main` de
  `cli.py`. É por isso que `uv run sauf-scraper` funciona. Parecido com `"scripts"` do
  `package.json`.

---

## 3. Por que existe a pasta `src/sauf_scraper/`?

- **`src/`** é o "src layout": o código fica separado de testes e configs. Isso obriga os
  testes a importarem o pacote instalado, e não arquivos soltos, o que evita o clássico
  "funciona na minha máquina".
- **`sauf_scraper`** (com underscore) é o nome do **pacote** Python. Nome de pacote não pode
  ter hífen, por isso o projeto se chama `sauf-scraper` e o pacote `sauf_scraper`.
- **`__init__.py`** marca uma pasta como pacote (como um `index.ts` que permite
  `import ... from "./core"`). Pode ficar vazio. No `sauf_scraper/__init__.py` ele só guarda
  a versão.

Os imports usam o caminho completo do pacote, como `from sauf_scraper.core.models import Curso`.
É o mesmo que `import br.com.sauf.core.models.Curso` em Java.

---

## 4. Arquivo por arquivo

### `cli.py`: ponto de entrada (CLI = Command Line Interface)

- Usa `argparse` (da biblioteca padrão) para ler `--ies`, `--dry-run` e `--listar`.
- Monta as dependências na mão: `Settings`, `HttpEducado` e o destino. Em Spring, quem faz
  isso é o container de injeção de dependência. Aqui, a gente monta explicitamente.
- Devolve um número (`return 0` ou `return 1`) que vira o **código de saída** do processo.
  Jenkins e cron entendem qualquer valor diferente de 0 como falha.
- `if __name__ == "__main__":` permite rodar o arquivo direto (`python cli.py`). Esse bloco
  só executa quando o arquivo é o programa principal, e não quando ele é importado.

### `core/`: o "núcleo", que não sabe nada de sites específicos

**`core/config.py`: configurações**
- A classe `Settings` herda de `BaseSettings` (pydantic-settings). Cada atributo vira uma
  variável de ambiente com prefixo `SAUF_`, por exemplo `api_base_url` → `SAUF_API_BASE_URL`.
- Lê do `.env` automaticamente e converte os tipos: `"2"` vira `2.0` em
  `request_delay_seconds: float`.
- `SecretStr` esconde o valor da API key em logs e prints (aparece `**********`).
- É o `application.properties` + `@ConfigurationProperties(prefix = "sauf")`.

**`core/models.py`: o contrato com o backend Java**
- **É o arquivo mais importante para a integração.** O JSON que o Java vai receber sai daqui.
- `SaufModel` é a classe base de todos os modelos e define três regras:
  - `alias_generator=to_camel`: no Python o campo é `duracao_texto` (snake_case, padrão
    Python), e no JSON sai `duracaoTexto` (camelCase, padrão do Jackson no Spring).
  - `extra="forbid"`: se alguém passar um campo que não existe, dá erro em vez de ignorar.
  - `str_strip_whitespace=True`: tira espaços das pontas dos textos, comum em HTML raspado.
- `Fonte`: de onde e quando o dado veio, para rastreabilidade.
- `Curso`: campos do DER, mais três campos de identidade:
  - `chave`: texto obrigatório gerado com `montar_chave_curso()`, ex.:
    `uem:engenharia-de-software:maringa:noturno`;
  - `codigo_emec`: código e-MEC do curso (`CO_CURSO` no Censo), **opcional**, porque cursos
    novos ainda não estão no Censo;
  - `url_origem`: link da página do curso, obrigatório (o botão "acessar o site").
  Além disso: `grau`, `modalidade`, `turno`, `duracao_texto` + `duracao_semestres` e `cidade`
  + `uf` do campus. A área **não** vai no lote: vem do rótulo Cine do Censo, no backend.
  O site da instituição é a fonte principal; o Censo só completa o que o site não mostra.
- `montar_chave_curso(*partes)`: tira acentos, deixa minúsculo e junta as partes com `:`.
  Os spiders devem usá-la sempre, para a mesma página gerar sempre a mesma chave.
- `Grau` e `Modalidade` são enums (`StrEnum` = enum cujo valor é texto). Os valores ficam em
  **minúsculas** (`presencial`, `tecnologo`), iguais aos do JSON da API.
  Veja como cada código do Censo vira um valor em [MAPEAMENTO_CENSO.md](MAPEAMENTO_CENSO.md).
- `LoteIngestao`: o pacote enviado em cada POST, com o `codigoEmecInstituicao` e todos os
  cursos da instituição. Os dados da instituição (nome, tipo, UF...) **não** vêm do scraper:
  eles são importados do Censo da Educação Superior em um fluxo separado, só para as
  instituições que têm spider. Se a instituição ainda não estiver cadastrada, a API recusa
  o lote e registra no log.
- `RespostaIngestao`: o que esperamos que a API devolva. Ela usa `extra="ignore"` porque, se
  o backend mandar campos a mais, não queremos quebrar.
- `Field(pattern=..., min_length=1)` são validações, como `@Pattern` e `@NotBlank` do Bean
  Validation.
- `str | None = None` significa "texto ou nulo, padrão nulo", ou seja, campo opcional. Em TS
  seria `cidade?: string | null`.

**`core/pipeline.py`: o orquestrador**
- A função `executar(...)` recebe a lista de spiders, o cliente HTTP e o destino, e roda um
  spider de cada vez dentro de um `try/except`.
- Separa dois tipos de erro:
  - `ValidationError`: o Pydantic recusou o dado. Normalmente significa que o site mudou de
    layout e o parser extraiu lixo ou nada.
  - `Exception`: qualquer outra falha (site fora do ar, timeout, API recusou).
- `@dataclass` gera construtor, `__repr__` e `__eq__` automaticamente, como o `record` do
  Java ou o `@Data` do Lombok. Usei em `ResultadoSpider` e `ResumoExecucao` porque são dados
  internos que não precisam de validação. Por isso não usei Pydantic aí.
- `@property houve_falha` é um "getter calculado": você acessa `resumo.houve_falha` sem
  parênteses.

**`core/logging.py`: log estruturado**
- Cada evento vira **uma linha de JSON** (`{"ts": ..., "level": ..., "msg": ...}`). Isso
  facilita filtrar no Jenkins ou contar quantos cursos cada execução trouxe.
- Para adicionar dados ao log: `logger.info("mensagem", extra={"dados": {"chave": valor}})`.
- O nome `logging.py` dentro de `core/` não conflita com o `logging` da biblioteca padrão,
  porque o import é sempre `sauf_scraper.core.logging`.

### `client/`: tudo que conversa com o mundo externo via HTTP

**`client/http.py`: `HttpEducado`**
- É o único jeito que os spiders têm de baixar páginas. Ele concentra as boas práticas:
  1. Coloca o `User-Agent` do bot em toda requisição.
  2. Baixa e guarda o `robots.txt` de cada domínio uma vez só. Se a URL for proibida, lança
     `BloqueadoPorRobotsError`.
  3. Garante o intervalo mínimo (`request_delay_seconds`) entre requisições ao mesmo site.
  4. Chama `raise_for_status()`, que transforma respostas 4xx/5xx em exceção.
- `requests.Session` reaproveita conexões e headers entre requisições, como uma instância
  configurada de `RestTemplate`.
- Atributos e métodos com `_` na frente (`_session`, `_permitido`) são **privados por
  convenção**. Python não tem `private` de verdade, então o underscore é o combinado para
  "não use isso de fora da classe".
- `**kwargs` repassa parâmetros extras para o `requests` (por exemplo, `params=`, `headers=`).
  É parecido com `...rest` no TS.

**`client/destinos.py`: para onde vai o lote**
- `Destino(Protocol)` é uma **interface estrutural**: qualquer classe com o método
  `enviar(lote)` "é" um `Destino`, sem precisar declarar `implements`. Funciona como as
  interfaces do TypeScript.
- `ApiSauf`: faz `POST {api_base_url}/api/v1/ingestao/lotes` com o header `X-Api-Key`. Se a
  API não responder 2xx, lança `ApiRecusouLoteError` com o status e o corpo da resposta.
- `ArquivoJson`: o modo `--dry-run`, que grava `output/emec-<codigo>.json`. Serve para desenvolver
  sem backend e para entregar ao front como mock.
- `model_dump(mode="json", by_alias=True)` converte o modelo Pydantic em dict pronto para
  JSON, com datas em ISO e nomes em camelCase. É o `ObjectMapper.writeValueAsString` do Java.

### `spiders/`: um arquivo por instituição **<--**

**`spiders/base.py`: a classe abstrata `Spider`**
- `ABC` + `@abstractmethod` funcionam como uma classe `abstract` em Java: quem herdar é
  **obrigado** a implementar `coletar()`, senão nem consegue instanciar.
- Todo spider recebe `self.http` (o `HttpEducado`) e `self.execucao_id`.
- No corpo da classe, cada spider define dois atributos:
  - `chave: str`: apelido curto, por exemplo `chave = "uel"`. É o que você digita em
    `--ies uel` e que aparece nos logs.
  - `codigo_emec: int`: código da instituição no e-MEC, por exemplo `codigo_emec = 57`. É ele
    que liga os cursos à instituição no backend.

**`spiders/__init__.py`: o registro**
- `SPIDERS` é um dicionário `{"uel": UelSpider, ...}`. O CLI usa esse dicionário para saber
  quais spiders existem. Hoje ele está vazio, e por isso o programa avisa "nenhum spider
  registrado".
- `codigos_emec()` devolve a lista de códigos e-MEC dos spiders registrados. É o filtro do
  import do CSV do e-MEC: só entram as instituições que têm spider (`--listar` mostra os dois).
- `type[Spider]` significa "a classe Spider (ou uma filha)", e não uma instância dela.

> **Por que o nome "spider"?** É o termo clássico de web scraping, porque o programa
> "anda pela teia" de links. Também é o nome usado pelo Scrapy, então se o time migrar no
> futuro, o vocabulário continua o mesmo.

### `parsers/`: converte HTML/JSON bruto em dados

- Hoje está vazia. Para cada instituição, vai existir um `parsers/<chave>.py` com funções
  que **recebem texto** (o HTML) e **devolvem dados**, sem fazer nenhuma requisição.
- Por que separar do spider? Porque assim dá para testar o parser com um HTML salvo em
  `tests/fixtures/`, sem internet, e o teste continua valendo mesmo se o site sair do ar.

---

## 5. Testes (`tests/`)

| Arquivo | O que verifica |
|---|---|
| `conftest.py` | **Fixtures** compartilhadas: `settings` (config de teste com delay 0 e pasta temporária) e `lote` (um lote de exemplo válido). O pytest injeta essas fixtures pelo nome do parâmetro, mais ou menos como o `@Autowired` em testes Spring |
| `test_models.py` | JSON sai em camelCase, nome vazio é recusado, chave inválida é recusada, campo inventado é recusado |
| `test_destinos.py` | POST vai com `X-Api-Key` e o corpo certo; erro 400 vira exceção; dry-run grava o arquivo |
| `test_http.py` | Respeita `robots.txt`, libera tudo quando não há `robots.txt` e manda o User-Agent |
| `test_pipeline.py` | Um spider que quebra e outro com dado inválido **não impedem** o terceiro de ser enviado |

- `responses` é uma biblioteca que **intercepta** as chamadas do `requests` e devolve
  respostas falsas, então nenhum teste acessa a internet. É parecido com `MockRestServiceServer`
  do Spring ou o `msw` no front.
- `tmp_path` é uma fixture nativa do pytest que cria uma pasta temporária por teste.
- No pytest, um teste é só uma função `test_...` com `assert`. Não precisa de classe nem de
  `assertEquals`.

---

## 6. Mini-glossário de Python que aparece no código

| Python | Significado | Em Java / TS |
|---|---|---|
| `def f(x: int) -> str:` | Função com type hints. Os tipos **não** são checados em tempo de execução, servem para o editor e para o Pydantic | `String f(int x)` |
| `self` | A própria instância, sempre o 1º parâmetro dos métodos | `this` |
| `__init__` | Construtor | construtor |
| `class A(B):` | A herda de B | `extends` |
| `str \| None` | Pode ser texto ou `None` | `String` anulável / `string \| null` |
| `list[Curso]`, `dict[str, float]` | Lista e mapa tipados | `List<Curso>`, `Map<String, Double>` |
| `None` | Nulo | `null` |
| `raise X` / `try/except` | Lançar e capturar exceção | `throw` / `try/catch` |
| `f"{a}://{b}"` | Template string | `` `${a}://${b}` `` |
| `"""texto"""` logo abaixo de `def`/`class` | Docstring: documentação que aparece no hover do editor | Javadoc |
| `@algo` em cima de função/classe | Decorator: "embrulha" a função ou classe com comportamento extra | parecido com annotations |
| `x or y` | Se `x` for "vazio" (`None`, `""`, `0`), usa `y` | `x ?? y` (quase) |

---

## 7. Onde você vai mexer primeiro

1. `spiders/<chave>.py` e `parsers/<chave>.py` da primeira instituição.
2. Registrar o spider em `spiders/__init__.py`.
3. Salvar um HTML real em `tests/fixtures/<chave>/` e escrever o teste do parser.
4. Rodar `uv run sauf-scraper --ies <chave> --dry-run` e abrir o `output/emec-<codigo>.json`.

Os arquivos de `core/` e `client/` você só precisa ler. Eles mudam quando as perguntas de
negócio forem respondidas (principalmente `models.py`).
