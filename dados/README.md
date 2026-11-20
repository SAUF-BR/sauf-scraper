# Dados manuais

Esta pasta guarda o que **nenhuma fonte oficial entrega pronto** e, por isso, o time cadastra à mão:

| O quê | Arquivo | Aparece no app |
|---|---|---|
| Ano de fundação, "sobre", site, logo e foto de capa de cada universidade | `ies/<sigla>.toml` + imagens em `ies/img/` | Lista e detalhe de universidades, favoritos |
| Uma imagem por área Cine | `areas.toml` + imagens em `areas/img/` | Card e página de cada curso da área |

Tudo é versionado no Git: quem mudou, quando e por quê fica no histórico. O scraper valida os
arquivos e envia para a API por uma rota de ingestão, do mesmo jeito que o Censo, o IGC e o Sisu.

> Decisões: D-98 a D-103 em `sauf-api/docs/DECISOES.md` e a ADR-BE-017 em `sauf-docs`.

---

## 1. Manual ou scraper?

Antes de cadastrar à mão, confira se o dado não vem de uma fonte automática:

| Dado | De onde vem | Manual? |
|---|---|---|
| Nome, sigla, cidade, endereço da sede | Censo (`sauf-scraper censo`) | Não |
| Cursos, turnos, duração, "sobre" do curso | Site da universidade (spiders) | Não |
| Nota MEC | IGC (`sauf-scraper igc`) | Não |
| Nota de corte | Sisu (`sauf-scraper sisu`) | Não |
| Ano de fundação, "sobre" da universidade, site | — | **Sim**, `ies/<sigla>.toml` |
| Logo e foto de capa da universidade | — | **Sim**, `ies/<sigla>.toml` |
| Imagem dos cursos | — | **Sim**, uma por área em `areas.toml` |

Regra geral: se existe uma fonte oficial que dá para ler com programa, escreva um importador. O
cadastro manual é para dados que mudam pouco e que só uma pessoa consegue escolher e conferir.

**O Censo e os spiders nunca apagam os dados manuais.** Rodar o `censo` de novo não mexe no ano de
fundação, no "sobre", no site nem nas imagens (há teste na API garantindo isso).

---

## 2. Por que TOML

Os arquivos são [TOML](https://toml.io/pt/v1.0.0), lidos pelo `tomllib`, que já vem com o Python.
Escolhemos TOML em vez de YAML porque:

- **não precisa de pacote novo**: o PyYAML não é dependência do scraper;
- **aceita texto de várias linhas** com `"""`, ótimo para os parágrafos do "sobre";
- é mais difícil errar: não depende de indentação e os textos ficam sempre entre aspas.

---

## 3. Universidade: `ies/<sigla>.toml`

O nome do arquivo é a sigla em minúsculas (`uem.toml`) e precisa bater com o campo `sigla`.
Modelo completo para copiar:

```toml
# Dados manuais da UEM. Como preencher e enviar: dados/README.md
# Conferido em 2026-11-20 nas fontes de [fontes]. Ano de fundação = criação legal (D-102):
# Lei Estadual nº 6.034, de 6 de novembro de 1969.

sigla = "UEM"
codigo_emec = 57
nome = "Universidade Estadual de Maringá"
ano_fundacao = 1969
site_url = "https://www.uem.br"

# Um item da lista = um parágrafo. Quebrar a linha dentro do parágrafo é só para caber na tela.
sobre = [
  """Primeiro parágrafo, que pode ocupar
várias linhas no arquivo.""",
  """Segundo parágrafo.""",
]

[fontes]
ano_fundacao = "https://www.uem.br/a-uem/historico"
sobre = [
  "https://www.uem.br/a-uem/historico",
]

[logo]
arquivo = "img/uem-logo.png"
autor = "Leonardossrocha"
licenca = "CC BY-SA 4.0"
licenca_url = "https://creativecommons.org/licenses/by-sa/4.0"
fonte_url = "https://commons.wikimedia.org/wiki/File:Logo_UEM_-_Universidade_Estadual_de_Maring%C3%A1.svg"

[capa]
arquivo = "img/uem-capa.webp"
autor = "Sobreira 10"
licenca = "CC0"
licenca_url = "https://creativecommons.org/publicdomain/zero/1.0/deed.en"
fonte_url = "https://commons.wikimedia.org/wiki/File:Bloco_D67.webp"
```

### Campo a campo

| Campo | Obrigatório | Regra |
|---|---|---|
| `sigla` | sim | Igual ao nome do arquivo (sem diferenciar maiúsculas). |
| `codigo_emec` | sim | Código da instituição no e-MEC (o mesmo do Censo). A universidade precisa já ter sido importada pelo `censo`. |
| `nome` | sim | Só para quem lê o arquivo. **Não** é enviado: o nome oficial vem do Censo. |
| `ano_fundacao` | sim | Ano da **criação legal** (veja abaixo). Não pode estar no futuro. |
| `site_url` | sim | Endereço completo, com `https://`. |
| `sobre` | sim | De 1 a 5 parágrafos, até 2000 caracteres cada, texto puro (sem HTML nem Markdown). |
| `[fontes]` | sim | Link de onde saiu o ano de fundação e links usados no "sobre". Quem for conferir abre esses links. |
| `[logo]`, `[capa]` | não | Se a seção não existir, a API **apaga** a imagem que tinha. |

### Ano de fundação = criação legal

Usamos o ano do **ato legal que criou a instituição com a forma que ela tem hoje**, do jeito que a
própria universidade o apresenta no site oficial. Exemplos do que já está cadastrado:

| Universidade | Ano | Ato |
|---|---|---|
| UEM | 1969 | Lei Estadual nº 6.034/1969 |
| UEL | 1970 | Decreto Estadual nº 18.110/1970 |
| UTFPR | 2005 | Lei Federal nº 11.184/2005 (transformou o Cefet-PR em universidade) |
| UFSC | 1960 | Lei Federal nº 3.849/1960 |
| UFSM | 1960 | Lei Federal nº 3.834-C/1960 |

Quando a instituição de origem é bem mais antiga, ela entra no **texto do "sobre"**, não no ano. A
UTFPR, por exemplo, tem 2005 como ano de fundação e o "sobre" conta a história desde a Escola de
Aprendizes Artífices de 1909. Escreva o ato no comentário do topo do arquivo.

### Como escrever o "sobre"

- Escreva com **suas palavras**, a partir do site oficial da universidade. Não copie parágrafos
  inteiros (direitos autorais) e não use Wikipédia como fonte do texto.
- 2 ou 3 parágrafos curtos: criação e origem; história e crescimento; como a universidade é hoje.
- Só fatos que estão nas fontes listadas em `[fontes]`. Nada de opinião ("a melhor do estado").
- Nada de dados pessoais além de figuras históricas públicas (ex.: o primeiro reitor).
- Coloque no comentário do topo a data em que conferiu as fontes.

---

## 4. Imagens: como escolher no Wikimedia Commons

Todas as imagens vêm do [Wikimedia Commons](https://commons.wikimedia.org), porque cada arquivo
tem a licença e o autor registrados na própria página. **Nunca** baixe logo ou foto do site da
universidade ou do Google Imagens: não sabemos a licença.

### Passo a passo

1. **Procure.** Comece pelo artigo da universidade na Wikipédia em português: o logo e as fotos que
   aparecem lá estão quase sempre no Commons. Outra opção é a categoria da universidade no Commons
   (ex.: "Category:Universidade Estadual de Londrina"). Para as áreas, busque fotos com
   "(Unsplash)" no nome: são CC0.
2. **Abra a página do arquivo** (clique na imagem e depois em "Mais detalhes"). O endereço começa com
   `https://commons.wikimedia.org/wiki/File:`. **Esse endereço vai em `fonte_url`.**
3. **Confira a licença** no quadro "Licensing" (Licenciamento), mais abaixo na página:

   | Licença | Pode usar? | O que preencher |
   |---|---|---|
   | Public domain, PD-textlogo, PD-ineligible | Sim, sem crédito obrigatório | `licenca = "Public domain"`, sem `licenca_url` |
   | CC0 | Sim, sem crédito obrigatório | `licenca = "CC0"` e o link do CC0 |
   | CC BY (2.0, 3.0, 4.0) | Sim, **com crédito** ao autor | `licenca = "CC BY 4.0"` e o link da licença |
   | CC BY-SA (2.0, 3.0, 4.0) | Sim, **com crédito** e mesma licença se alguém modificar a imagem | `licenca = "CC BY-SA 4.0"` e o link |
   | "Fair use", "Non-free", arquivo só na Wikipédia (não no Commons) | **Não** | Procure outra imagem |
   | CC BY-NC, CC BY-ND | **Não** (proíbem uso comercial ou adaptação) | Procure outra imagem |

   Se aparecer o aviso **"trademarked"** (marca registrada), a licença vale para o arquivo, mas a
   marca continua sendo da instituição: pode usar para identificar a universidade, como fazemos.
4. **Pegue o autor** no campo "Author" (Autor) e a licença no campo do quadro de licença. Copie o
   nome do autor como está (é o crédito que a licença pede).
5. **Baixe num tamanho razoável.** Clique em "Download" (Baixar) acima da imagem e escolha:
   - logo: cerca de **500 px** de largura, em **PNG** (se o original for SVG, o Commons gera o PNG);
   - capa e área: cerca de **1280 px** de largura (máximo 1600), em JPG ou WebP.

   O limite é **2 MB** por imagem, e só JPG, PNG e WebP são aceitos. **SVG não serve**: baixe o PNG.
6. **Salve** em `ies/img/<sigla>-logo.png`, `ies/img/<sigla>-capa.jpg` ou
   `areas/img/<codigo>-<nome>.jpg` e preencha a seção no TOML.
7. **Registre o link** em `docs/FONTES.md` (toda URL acessada para o SAUF vai lá, com a data).

### Crédito no app

As licenças CC BY e CC BY-SA pedem que o autor apareça junto da imagem. A API guarda autor,
licença, link da licença e página de origem de cada imagem. **A forma de mostrar o crédito no front
ainda está em aberto** (P-11 no DECISOES); até lá, os créditos ficam nos TOML e no banco.

---

## 5. Imagem de uma área: `areas.toml`

Um bloco `[[area]]` por área Cine que existe no banco (hoje, 00 a 10):

```toml
[[area]]
codigo_cine = "07"
nome = "Engenharia, produção e construção"

[area.imagem]
arquivo = "areas/img/07-engenharia.jpg"
autor = "Nome do autor, como aparece no campo Author do Commons"
licenca = "CC0"
licenca_url = "https://creativecommons.org/publicdomain/zero/1.0/deed.en"
fonte_url = "https://commons.wikimedia.org/wiki/File:View_Above_Construction_Site_(Unsplash).jpg"
```

- `codigo_cine` tem sempre 2 dígitos ("07", não "7") e não pode repetir.
- `nome` é só para quem lê o arquivo.
- A imagem da área aparece em **todos os cursos da área**. Se um dia houver imagem por curso, a do
  curso tem prioridade e a da área fica de reserva (D-101).
- Prefira fotos sem pessoas identificáveis em primeiro plano ou de bancos com autorização de uso
  (as fotos "(Unsplash)" do Commons são CC0).
- A rota da API não apaga imagem de área: para trocar, mude o arquivo e envie de novo.
- Área sem `[area.imagem]` é aceita e fica **de fora do envio** (o comando mostra "sem imagem,
  não enviada"). Imagem escolhida mas ainda não baixada fica num comentário no lugar da seção,
  com o nome do arquivo e a página do Commons (`# [area.imagem] pendente ...`): baixe, troque o
  comentário pela seção completa e envie. O mesmo vale para `[logo]` e `[capa]` das
  universidades, com uma diferença: **sem a seção, a API apaga** a imagem que já estava lá.

---

## 6. Validar sem enviar

Rode sempre o `--dry-run` antes de enviar. Ele valida tudo e não fala com a API:

```bash
uv run sauf-scraper ies --dry-run
uv run sauf-scraper ies --sigla UEM --dry-run
uv run sauf-scraper areas --dry-run
```

Para a universidade, o dry-run grava `output/ies-<sigla>.json` com o que seria enviado. Os testes
também conferem os arquivos reais desta pasta:

```bash
uv run pytest tests/test_manuais.py
```

---

## 7. Enviar para a API

O envio usa as mesmas variáveis do `.env` dos outros comandos (`SAUF_API_BASE_URL` e
`SAUF_API_KEY`). Cada envio **substitui** o bloco inteiro da universidade (é um `PUT`): o que
saiu do arquivo some da API. Reenviar sem mudanças não altera nada.

```bash
uv run sauf-scraper ies
uv run sauf-scraper ies --sigla UEL UFSC
uv run sauf-scraper areas
uv run sauf-scraper areas --codigo 07 09
```

Ordem: o `censo` precisa ter rodado antes (ele cadastra as universidades e as áreas). Sem isso, a API
responde **422** "não está cadastrada".

- **Local:** API rodando na sua máquina contra o Postgres do Docker (ADR-BE-004).
- **Supabase (produção):** **só o Carlos executa**, com o `.env` de produção.

---

## 8. Conferir no app

Com a API e o front rodando:

1. **Universidades** (lista): o logo aparece no card.
2. **Detalhe da universidade**: capa, logo, ano de fundação e os parágrafos do "sobre".
3. **Favoritos > Universidades**: o logo aparece no card.
4. **Cursos**: a API manda a imagem da área em `imagemUrl`; quais telas já mostram está no
   relatório do TR-343.

Direto na API:

```bash
curl http://localhost:8080/api/v1/universidades?busca=UEM
```

As imagens são públicas: `GET /api/v1/universidades/{id}/logo`, `/capa` e
`GET /api/v1/areas/{id}/imagem`. A URL que a API devolve termina em `?v=<código>`, que muda quando a
imagem muda (assim o navegador não mostra a antiga do cache).

---

## 9. Corrigir um dado

1. Edite o TOML (ou troque a imagem em `img/`).
2. `uv run sauf-scraper ies --sigla <SIGLA> --dry-run`.
3. Envie (`uv run sauf-scraper ies --sigla <SIGLA>`).
4. Commit `TR-<n> Descrição` com o arquivo e a imagem.

Para **remover** o logo ou a capa, apague a seção `[logo]`/`[capa]` do TOML e envie: a API apaga a
imagem. Para remover o "sobre" inteiro não há atalho: o campo é obrigatório no arquivo.

---

## 10. Erros comuns

| Mensagem | O que fazer |
|---|---|
| `a sigla 'X' não bate com o nome do arquivo` | Renomeie o arquivo ou corrija `sigla`. |
| `imagem não encontrada em ...` | O caminho em `arquivo` é relativo à pasta do TOML (`img/...` para universidades, `areas/img/...` para áreas). |
| `não é JPG, PNG nem WebP (SVG não serve...)` | Baixe o PNG no Commons em vez do SVG. |
| `o limite é 2 MB` | Baixe um tamanho menor no Commons. |
| `use a página do arquivo no Wikimedia Commons` | `fonte_url` precisa começar com `https://commons.wikimedia.org/wiki/File:`. |
| `cada parágrafo vai num item separado da lista` | Linha em branco dentro de um parágrafo: divida em dois itens. |
| `Extra inputs are not permitted` | Campo com nome errado (ex.: `ano` em vez de `ano_fundacao`). |
| `TOML inválido` | Aspas ou colchetes sem fechar; a mensagem diz a linha. |
| API **401** | `SAUF_API_KEY` ausente ou errada no `.env`. |
| API **422** "não está cadastrada" | Rode o `censo` antes. |
| API **400** | A mensagem diz o campo; normalmente o scraper já pega antes. |
