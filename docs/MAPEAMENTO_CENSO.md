# Mapeamento: Censo da Educação Superior (INEP) → modelo do SAUF

Este documento descreve como os microdados do Censo da Educação Superior viram
instituições e cursos no SAUF. Ele serve para quem for implementar o **import** (seja na
API Java ou em um comando Python separado) e para quem escreve os **spiders**.

## 1. Quem faz o quê

| Dado | Fonte | Responsável |
|---|---|---|
| Instituição (nome, UF, tipo...) | Censo, arquivo de IES | Import |
| Cursos com código e-MEC, grau, modalidade, cidade, vagas, área Cine, gratuidade | Censo, arquivo de cursos | Import |
| Cursos como aparecem no site (nome, duração, turno, descrição, **link da página**...) | Site da instituição | Scraper |

Regras de negócio (decididas pelo Carlos em 05 e 06/10/2026):

1. O import traz **só as instituições que têm spider**. A lista de códigos vem de
   `sauf_scraper.spiders.codigos_emec()` (ou de `uv run sauf-scraper --listar`).
2. O **site da instituição é a fonte principal** dos cursos. O objetivo é dizer ao
   usuário "esta universidade oferece este curso, temos estas informações, acesse o site".
3. Lote de uma instituição que não está cadastrada → a API **recusa e registra no log**.
4. Curso encontrado no site e que **não** está no Censo (ex.: curso criado depois do ano do
   Censo) é **aceito**, só com as informações do site e com `codigosEmec` vazio.
5. Quando site e Censo **discordam**, vale o site. O Censo só **completa** o que o site não
   mostra (vagas, área Cine, gratuidade).

### Identidade do curso (como o backend evita duplicar)

Cada curso enviado pelo scraper tem:

| Campo | Obrigatório | Papel |
|---|---|---|
| `chave` | sim | chave natural gerada pelo spider com `montar_chave_curso()`, ex.: `uem:engenharia-de-software:maringa:noturno`. Identidade do curso (uma página): upsert por (instituição + `chave`) |
| `codigosEmec` | não | lista dos códigos e-MEC (`CO_CURSO`) que a página cobre (D-35). Só liga o curso ao Censo; não é identidade |
| `urlOrigem` | sim | link da página do curso no site da instituição (botão "acessar o site") |

O hash que aparece em algumas URLs (ex.: UEM `.../curso/a99a3305...`) **não** é usado como
identidade, porque não dá para garantir que ele nunca muda. Se a URL mudar, o próximo
scraping só atualiza `urlOrigem`.

## 2. Os arquivos

O pacote vem do site do INEP (Microdados → Censo da Educação Superior), um `.zip` por ano.
Na pasta `dados/`:

| Arquivo | Tamanho (2024) | Uma linha por... |
|---|---|---|
| `MICRODADOS_ED_SUP_IES_<ano>.CSV` | ~1 MB, 2.561 linhas | instituição (`CO_IES` é único) |
| `MICRODADOS_CADASTRO_CURSOS_<ano>.CSV` | ~450 MB, ~720 mil linhas | curso **por local de oferta** (ver §4) |

O dicionário de dados fica em `Anexos/ANEXO I - Dicionário de Dados/`.

> A pasta do Censo está no `.gitignore`. **Nunca** commite esses arquivos.

### Formato

- Separador: `;`
- Encoding: **Latin-1** (ISO-8859-1), **não** UTF-8. Ler como UTF-8 quebra os acentos
  (`UNIVERSIDADE FEDERAL DE UBERLÃ‚NDIA`) ou dá erro.
  - Python: `open(caminho, encoding="latin-1", newline="")` + `csv.DictReader(f, delimiter=";")`
  - Java: `new InputStreamReader(in, StandardCharsets.ISO_8859_1)`
- Primeira linha é o cabeçalho com os nomes das colunas.
- O arquivo de cursos é grande: leia **linha a linha** (streaming), filtrando por `CO_IES`,
  em vez de carregar tudo na memória.

## 3. Instituição (arquivo de IES)

| Coluna do Censo | Campo no SAUF | Observação |
|---|---|---|
| `CO_IES` | código e-MEC da instituição | chave do upsert; é o `codigoEmecInstituicao` do lote do scraper |
| `NO_IES` | nome | |
| `SG_IES` | sigla | |
| `SG_UF_IES` | UF | da sede/reitoria |
| `NO_MUNICIPIO_IES` | cidade | da sede/reitoria |
| `CO_MUNICIPIO_IES` | código IBGE da cidade | opcional, útil para filtros |
| `TP_REDE` | tipo | 1 = `publica`, 2 = `privada` |
| `TP_CATEGORIA_ADMINISTRATIVA` | categoria (opcional) | 1 Pública Federal, 2 Pública Estadual, 3 Pública Municipal, 4 Privada com fins lucrativos, 5 Privada sem fins lucrativos, 7 Especial |
| `TP_ORGANIZACAO_ACADEMICA` | organização acadêmica (opcional) | 1 Universidade, 2 Centro Universitário, 3 Faculdade, 4 Instituto Federal, 5 CEFET |
| `NU_ANO_CENSO` | ano de referência | guardar para mostrar "Fonte: Censo 2024" |

As colunas `QT_TEC_*`, `QT_DOC_*` e de biblioteca não são usadas.

Exemplos (Censo 2024): UEL = 9, UFU = 17, USP = 55, UEM = 57, UFPR = 571.

## 4. Curso (arquivo de cursos)

### ⚠️ Deduplicação por `CO_CURSO`

O arquivo **não** tem uma linha por curso. Cursos a distância aparecem **uma vez por
município de polo**, além de uma linha consolidada. A coluna `TP_DIMENSAO` indica o tipo:

| `TP_DIMENSAO` | Significado | Linhas em 2024 |
|---|---|---|
| 1 | Curso presencial ofertado no Brasil | 34.824 |
| 2 | Curso a distância, **por município de polo** | 673.756 |
| 3 | Curso a distância, consolidado no nível Brasil (sem município) | 11.319 |
| 4 | Curso a distância ofertado no exterior | 450 |

São ~720 mil linhas para apenas **46.150 códigos de curso distintos**. Exemplo: o curso
"Computação" EAD da UEL (`CO_CURSO` 1343863) aparece em Assaí, Astorga, Bandeirantes...

Regra do import: **um curso por `CO_CURSO`**.

- Presencial (`TP_DIMENSAO` = 1): usar a própria linha. Em 2024, cada curso presencial tem
  exatamente uma linha.
- EAD: usar a linha consolidada (`TP_DIMENSAO` = 3). Em 2024, nenhum curso tem mais de uma.
  As linhas com `TP_DIMENSAO` = 2 podem virar, no futuro, a lista de polos do curso, mas
  não criam cursos novos.
- EAD **sem** linha consolidada (7 cursos em 2024): usar a primeira linha com
  `TP_DIMENSAO` = 2, ignorando cidade/UF, e logar o código.
- Nenhum curso mistura presencial (1) e EAD (2/3/4) no mesmo `CO_CURSO`.

### Colunas

| Coluna do Censo | Campo no SAUF | Observação |
|---|---|---|
| `CO_CURSO` | `codigoEmec` do curso do Censo | inteiro > 0; já diferencia campus, grau e modalidade; o curso do site leva a lista em `codigosEmec` |
| `CO_IES` | instituição do curso | filtrar só as IES que têm spider |
| `NO_CURSO` | `Curso.nome` | |
| `TP_GRAU_ACADEMICO` | `grau` do curso do Censo | 1 `bacharelado`, 2 `licenciatura`, 3 `tecnologo`, 4 `bacharelado_e_licenciatura`; vazio = não se aplica (ex.: área básica de ingresso) |
| `TP_MODALIDADE_ENSINO` | `modalidade` do curso do Censo | 1 `presencial`, 2 `ead`. `semipresencial` (Decreto 12.456/2025) ainda não existe no Censo 2024 |
| `CO_CINE_ROTULO`, `NO_CINE_ROTULO` | curso genérico do catálogo | agrupa as ofertas no catálogo (ver "Curso genérico" abaixo) |
| `CO_CINE_AREA_GERAL`, `NO_CINE_AREA_GERAL` | área do curso genérico | classificação oficial Cine/Unesco (ex.: "Engenharia, produção e construção") |
| `NO_MUNICIPIO`, `CO_MUNICIPIO`, `SG_UF` | cidade/UF do curso | vazio para EAD consolidado |
| `IN_GRATUITO` | gratuito | 0 = não, 1 = sim |
| `QT_VG_TOTAL` | vagas | número do ano do Censo |
| `TP_NIVEL_ACADEMICO` | filtro | 1 = Graduação, 2 = Sequencial. Importar só 1 |
| `NU_ANO_CENSO` | ano de referência | |

As colunas `QT_INSCRITO_*`, `QT_ING_*`, `QT_MAT_*`, `QT_CONC_*` etc. são estatísticas de
alunos e não são usadas por enquanto.

### Curso genérico do catálogo: "Cine + nome amigável" (decidido em 06/10/2026)

O catálogo da API tem dois níveis: o **curso genérico** (o card "Biomedicina") e a **oferta**
(Biomedicina na UEM). O curso genérico é definido assim:

- O **rótulo Cine** do Censo (`CO_CINE_ROTULO`) **agrupa** as ofertas e define a **área**
  (`CO_CINE_AREA_GERAL`). São 353 rótulos no país.
- Uma **tabela pequena, revisada à mão**, dá o **nome exibido** no card, porque alguns rótulos
  são técnicos. Exemplo da UEM: "Contabilidade" (de "Ciências Contábeis").
- **D-36:** "X formação de professor" (licenciatura) entra no mesmo curso genérico que "X",
  com a área do bacharelado. Ex.: "Biologia formação de professor" → "Biologia".

Por isso o lote do scraper **não** manda área: ela vem do Censo, no backend.

### Contrato do curso no lote do scraper

| Campo (JSON) | Origem | Observação |
|---|---|---|
| `chave`, `codigosEmec`, `urlOrigem`, `nome` | site / tabela de casamento | ver "Identidade do curso" |
| `opcoes` | site | lista `[{grau, turno}]` com os graus que a página oferece (D-34); grau em minúsculas |
| `modalidade` | site | enum **em minúsculas**, igual ao da API (D-30 do `sauf-api`) |
| `turno` | site | texto da página, ex.: "Integral ou Noturno" |
| `sobre` | site | texto da seção "Sobre o Curso", **sem HTML**: `\n` entre linhas, `\n\n` entre parágrafos; `null` se a página não tiver a seção (D-37 no `sauf-api`, provisório) |
| `mercadoTrabalho` | site | texto das seções "Mercado de Trabalho" e "Campo de atuação" (juntas, na ordem da página), no mesmo formato do `sobre`; `null` se a página não tiver nenhuma das duas (D-46 e D-47 no `sauf-api`) |
| `duracaoTexto` | site | ex.: `"5 anos"` |
| `duracaoSemestres` | site | inteiro > 0, quando der para converter |
| `cidade`, `uf` | site | campus da oferta; `uf` com 2 letras maiúsculas |

### O que o Censo NÃO tem (fica para o scraper)

- duração do curso
- turno (o Censo só tem vagas diurno/noturno, não o turno em si)
- formas de ingresso (vestibular, SiSU, PAS...)
- descrição e link da página do curso
- notas de corte
- cursos criados depois do ano do Censo (o scraper envia sem `codigosEmec` e a API aceita;
  quando o Censo do ano seguinte trouxer o código, o curso pode ser ligado a ele)

## 5. Como rodar o import

O import é o comando `sauf-scraper censo` (código em `src/sauf_scraper/censo/`). Ele lê só as
instituições que têm spider (`codigos_emec()`), aplica as regras deste documento e envia o
resultado para `POST /api/v1/ingestao/censo`.

```
uv run sauf-scraper censo --mostrar      # imprime instituições e ofertas na tela
uv run sauf-scraper censo --dry-run      # grava output/censo-<ano>.json
uv run sauf-scraper censo                # envia para a API (precisa de SAUF_API_KEY)
```

A pasta dos microdados vem de `SAUF_CENSO_DIR` (padrão:
`microdados_censo_da_educacao_superior_2024`) ou de `--pasta`. Com o Censo 2024 e só a UEM,
leva uns 20 segundos e gera 1 instituição e 93 ofertas.

Formato enviado (JSON, camelCase):

- `anoCenso`
- `instituicoes[]`: `codigoEmec`, `nome`, `sigla`, `tipo` (`publica`/`privada`),
  `categoriaAdministrativa`, `organizacaoAcademica`, `uf`, `cidade`
- `ofertas[]`: `codigoEmec`, `codigoEmecInstituicao`, `nome`, `grau`, `modalidade`, `cidade`,
  `uf`, `vagas`, `gratuito`, `codigoCineRotulo`, `nomeCineRotulo`, `codigoCineArea`

### O site manda, o Censo complementa (D-33, 08/10/2026)

> "Dê preferência ao que está no site da UEM, é o mais atualizado. Vamos usar o CSV como
> complemento apenas. 2024 para 2026 é muito tempo para confiarmos no senso." (Carlos)

- A tabela de casamento só confirma códigos cujo grau/turno aparece na página do site.
- Os graus e turnos de cada curso vêm da página; os do Censo só entram quando a página não
  informa.
- Na API, o Censo **não cria ofertas**: os cursos dele ficam numa tabela à parte e só
  completam as ofertas do site com área, vagas e gratuidade.

### Uma página = um curso (D-34, D-35, D-36, 08/10/2026)

- **D-34:** cada página do site vira **um** curso no lote, com a lista de `opcoes` que a página
  mostra, cada uma com `grau` e `turno`. Ex.: Educação Física na UEM →
  `[{licenciatura, "Integral ou Noturno"}, {bacharelado, "Integral"}]`.
- **D-35:** os códigos e-MEC confirmados da página vão em `codigosEmec` (lista). É uso interno:
  o backend usa para puxar área, vagas (soma) e gratuidade do Censo, e a API não mostra.
- **D-36:** no backend, bacharelado e "formação de professor" do mesmo curso ficam no mesmo
  curso genérico, com a área do bacharelado (ex.: "Física", Ciências naturais).
- Quando a página não informa grau, o spider usa os graus dos códigos confirmados.

### Tabela de casamento: página do site → `CO_CURSO`

O spider não sabe o código e-MEC de cada página. Sem ele, o backend não consegue completar
o curso com área, vagas e gratuidade do Censo. A ligação fica numa tabela por instituição,
gerada automaticamente e revisada à mão:

`src/sauf_scraper/spiders/dados/<ies>_codigos.csv` (UTF-8, `;`), com **uma linha por par
página × código**: `chave`, `nome_site`, `cidade`, `turno_site`, `grau_site`, `status`,
`codigo_emec`, `nome_censo`, `grau_censo`, `vagas_diurno`, `vagas_noturno`, `sugestao`,
`confirmado`. Para revisar no Excel basta trocar `confirmado` de `nao` para `sim` nas linhas
certas.

```
uv run sauf-scraper --ies uem --dry-run   # 1º: coleta o site e grava output/emec-57.json
uv run sauf-scraper casar --ies uem       # 2º: gera/atualiza spiders/dados/uem_codigos.csv
```

Como o casamento é feito (só cursos presenciais de graduação da mesma IES no Censo):

1. mesmo **nome** (sem acentos/maiúsculas) e mesma **cidade** do campus;
2. se sobrar mais de um, desempata pelo **grau** do site;
3. se ainda sobrar, desempata pelo **turno** usando as vagas diurnas/noturnas do Censo
   (só quando o site traz um turno só, ex.: "Noturno").

| `status` | Significado | `confirmado` |
|---|---|---|
| `direto` | um único candidato | `sim` (o spider já usa) |
| `ambiguo` | mais de um candidato: uma linha para cada, com `sugestao` | `nao`: confirmar os códigos que a página cobre |
| `sem_par` | nenhum candidato (curso novo ou nome diferente no Censo) | `nao`: preencher `codigo_emec` à mão se achar o código |

`sugestao` nas linhas ambíguas:

- "uma página, vários": os candidatos diferem em grau ou turno (ex.: Física bacharelado e
  licenciatura). Normalmente se confirma todos.
- "habilitações diferentes? decidir": mesmo grau e turno (ex.: Engenharia de Produção com
  4 códigos). Precisa de conferência no e-MEC antes de confirmar.

Todos os códigos confirmados de uma página vão juntos na lista `codigosEmec` do mesmo curso
(D-34, D-35). O spider só usa as linhas com `confirmado = sim`. Rodar `casar` de novo **preserva** as
páginas que têm alguma linha confirmada à mão.

## 6. Atualização

- O INEP publica o Censo uma vez por ano. Os dados de um ano saem por volta do fim do ano
  seguinte (o Censo 2024 é o mais recente em 10/2026).
- O import deve ser **idempotente**: rodar de novo com o mesmo arquivo não muda nada;
  rodar com o arquivo do ano seguinte cria/atualiza pelo código e-MEC.
- Instituição ou curso que sumir do Censo novo deve ser marcado como **inativo**, não
  apagado.

## 7. Em aberto

- Curso do site que **não** está no Censo e não bate com nenhum curso genérico (ex.:
  Engenharia de Software da UEM): criar curso genérico novo? Com qual área?
- Conversão da duração para semestres: **provisório**, feita no scraper (`semestres_de_texto`),
  mantendo o texto original em `duracaoTexto` (P-25 no `sauf-api`).
- Oferta que some do site na coleta seguinte: marcar como inativa?

- Revisão das linhas **ambíguas** e **sem par** da tabela de casamento da UEM (ver abaixo).
- Como ligar um curso que entrou sem código e-MEC ao código que aparecer num Censo futuro
  (automático pela tabela do spider, ou manual).
