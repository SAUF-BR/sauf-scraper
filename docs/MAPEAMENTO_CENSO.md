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
   Censo) é **aceito**, só com as informações do site e sem `codigoEmec`.
5. Quando site e Censo **discordam**, vale o site. O Censo só **completa** o que o site não
   mostra (vagas, área Cine, gratuidade).

### Identidade do curso (como o backend evita duplicar)

Cada curso enviado pelo scraper tem:

| Campo | Obrigatório | Papel |
|---|---|---|
| `codigoEmec` | não | código e-MEC (`CO_CURSO`). Quando existe, é a identidade principal e liga o curso ao Censo |
| `chave` | sim | chave natural gerada pelo spider com `montar_chave_curso()`, ex.: `uem:engenharia-de-software:maringa:noturno`. Identidade do curso quando não há código e-MEC: upsert por (instituição + `chave`) |
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
| `TP_REDE` | tipo | 1 = `PUBLICA`, 2 = `PRIVADA` |
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
| `CO_CURSO` | `Curso.codigoEmec` | código e-MEC do curso; inteiro > 0; já diferencia campus, grau e modalidade |
| `CO_IES` | instituição do curso | filtrar só as IES que têm spider |
| `NO_CURSO` | `Curso.nome` | |
| `TP_GRAU_ACADEMICO` | `Curso.grau` | 1 `BACHARELADO`, 2 `LICENCIATURA`, 3 `TECNOLOGICO`, 4 `BACHARELADO_E_LICENCIATURA`; vazio = não se aplica (ex.: área básica de ingresso) |
| `TP_MODALIDADE_ENSINO` | `Curso.modalidade` | 1 `PRESENCIAL`, 2 `EAD`. `SEMIPRESENCIAL` (Decreto 12.456/2025) ainda não existe no Censo 2024 |
| `NO_CINE_AREA_GERAL` | `Curso.areaConhecimento` | classificação oficial Cine/Unesco (ex.: "Engenharia, produção e construção") |
| `NO_MUNICIPIO`, `CO_MUNICIPIO`, `SG_UF` | cidade/UF do curso | vazio para EAD consolidado |
| `IN_GRATUITO` | gratuito | 0 = não, 1 = sim |
| `QT_VG_TOTAL` | vagas | número do ano do Censo |
| `TP_NIVEL_ACADEMICO` | filtro | 1 = Graduação, 2 = Sequencial. Importar só 1 |
| `NU_ANO_CENSO` | ano de referência | |

As colunas `QT_INSCRITO_*`, `QT_ING_*`, `QT_MAT_*`, `QT_CONC_*` etc. são estatísticas de
alunos e não são usadas por enquanto.

### O que o Censo NÃO tem (fica para o scraper)

- duração do curso
- turno (o Censo só tem vagas diurno/noturno, não o turno em si)
- formas de ingresso (vestibular, SiSU, PAS...)
- descrição e link da página do curso
- notas de corte
- cursos criados depois do ano do Censo (o scraper envia sem `codigoEmec` e a API aceita;
  quando o Censo do ano seguinte trouxer o código, o curso pode ser ligado a ele)

## 5. Atualização

- O INEP publica o Censo uma vez por ano. Os dados de um ano saem por volta do fim do ano
  seguinte (o Censo 2024 é o mais recente em 10/2026).
- O import deve ser **idempotente**: rodar de novo com o mesmo arquivo não muda nada;
  rodar com o arquivo do ano seguinte cria/atualiza pelo código e-MEC.
- Instituição ou curso que sumir do Censo novo deve ser marcado como **inativo**, não
  apagado.

## 6. Em aberto

- Onde o import roda: API Java ou comando Python separado no `sauf-scraper`.
- Como o spider descobre o `CO_CURSO` de cada página do site (casando nome + grau + campus
  com o Censo, ou mantendo uma tabela fixa por instituição). Sugestão para a prova de
  conceito: tabela fixa por instituição.
- Curso que está no Censo mas **não** aparece no site (ex.: cursos EAD, ou um curso em
  extinção): mostramos para o usuário mesmo assim, só com os dados do Censo, ou não?
- Como ligar um curso que entrou sem código e-MEC ao código que aparecer num Censo futuro
  (automático pela tabela do spider, ou manual).
