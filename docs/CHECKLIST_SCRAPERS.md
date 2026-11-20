# Checklist dos scrapers

O que existe, o que falta e o que cada scraper entrega (base: análise do protótipo e
D-38 a D-47). Como criar um spider: [CONTRIBUTING.md](../CONTRIBUTING.md). Atualizado em 07/11/2026.

Legenda: ✅ feito · 🟡 com pendência · 🔜 próxima · ❌ falta · ⏸️ adiado/fora do MVP · 🚫 fora do plano · ➖ não se aplica

---

## 1. Scrapers específicos (um por IES)

**Meta da apresentação:** cerca de **5 IES completas**, com informação completa, em vez de
muitas IES com poucos dados (P-35, opção c → D-43).

### 1.1. UEM: Universidade Estadual de Maringá (e-MEC 57, `--ies uem`) 🟡

| Item | Estado | Observação |
|---|---|---|
| Lista de cursos: nome, campus/cidade/UF, link (`urlOrigem`) | ✅ | 67 páginas de cursos presenciais. |
| Grau + turno (`opcoes`) | ✅ | Uma página = um curso, com as opções da página (D-34). |
| Modalidade | ✅ | Todos `presencial`: a lista da UEM coletada é a de cursos presenciais. |
| Duração em semestres | ✅ | `duracaoSemestres` quando o texto é simples; o original fica em `duracaoTexto`. |
| `sobre` | ✅ | Texto puro (D-37). |
| `mercadoTrabalho` | ✅ | Seções "Mercado de trabalho" e "Campo de atuação", em negrito ou como linha solta (D-46, D-47). Cursos sem nenhuma das duas seções ficam `null`. |
| Casamento com códigos e-MEC | 🟡 | `spiders/dados/uem_codigos.csv`: 67 páginas, pendências abaixo. |
| Vagas e gratuidade | ✅ | Vêm do Censo pelo casamento. |
| Formas de ingresso (vestibular, PAS, SISU, transferência) | ❌ | Opcional. |
| Calendário do vestibular + link do edital | ⏸️ | Calendário adiado (P-33). |
| Nota de corte própria (vestibular) | ❌ | Opcional. A nota do SISU vem do scraper geral G3. |
| Disciplinas ("Você vai ter aulas de") | ❌ | Opcional. A página tem link para o PDF do Projeto Pedagógico. Exibir texto do site, não tags (D-41). |
| Mensalidade | ➖ | Pública e gratuita. |

**Pendências da UEM:**

- [ ] **Engenharia de Produção (Maringá):** a página não lista habilitações e o Censo tem
  **4 códigos** (21629, 22005, 22006, 22007). Conferir no e-MEC qual código é o curso do
  site e marcar `confirmado = sim` no CSV.
- [ ] **9 páginas sem par no Censo** (`sem_par`, `confirmado = nao`). Entram no catálogo
  ligadas a um curso genérico criado pelo nome do site, sem área e marcado
  `pendente_revisao` (comportamento provisório da P-05):
  Arquitetura e Urbanismo (CAU) (Umuarama), Engenharia de Computação (Umuarama),
  Engenharia de Controle e Automação - Inteligência Artificial, Engenharia de Software,
  Engenharia Têxtil, Letras, Nutrição, Serviço Social (Maringá) e Tecnologia em Gastronomia
  (Umuarama). Para cada uma: achar o código e-MEC à mão, se existir, ou decidir área e
  curso genérico (a definir, P-05).

### 1.2. UEL: Universidade Estadual de Londrina (e-MEC 9, `--ies uel`) 🟡

| Item | Estado | Observação |
|---|---|---|
| Lista de cursos: nome, cidade/UF, link (`urlOrigem`) | ✅ | 46 cursos com página em graduacao.uel.br (campus único, Londrina). Ficam de fora 2 EaD (site do NEAD) e 3 "(novo curso)" sem página. |
| Grau + turno (`opcoes`) | ✅ | Uma opção por grau, com os turnos das colunas desse grau ("Matutino ou Noturno", como na UEM; a API guarda uma opção por grau); "Bacharelado e Licenciatura" vira duas opções. |
| Modalidade | ✅ | Todos `presencial`. |
| Duração em semestres | 🟡 | "4.5 ANOS" → 9. Física e Química têm durações diferentes por grau: o texto lista cada uma e `duracaoSemestres` fica vazio. |
| `sobre` | 🟡 | Só a frase de chamada do cabeçalho (~200 caracteres). |
| `mercadoTrabalho` | ➖ | O site não tem a seção; fica `null`. |
| Vagas | 🟡 | O site informa por turno, mas o modelo do lote não tem campo de vagas: vêm do Censo. |
| Casamento com códigos e-MEC | ✅ | `spiders/dados/uel_codigos.csv`: 39 diretos + 7 páginas "bacharelado + licenciatura" (14 linhas), todas confirmadas; nenhum sem par. |

**Decisões do Carlos sobre a UEL (31/10/2026):** `sobre` = frase de chamada do site;
`mercadoTrabalho` fica vazio; cursos novos sem página e cursos EaD ficam de fora; Física e
Química ficam sem `duracaoSemestres` (o texto lista as duas durações); vagas continuam vindo
do Censo (sem mudar o contrato da API); o código 50017031 do Sisu ("ABI - Educação Física")
fica de fora da tabela de casamento.

### 1.3. UTFPR: Universidade Tecnológica Federal do Paraná (e-MEC 588, `--ies utfpr`) 🟡

| Item | Estado | Observação |
|---|---|---|
| Lista de cursos: nome, cidade/UF, link (`urlOrigem`) | ✅ | 121 cursos em 13 campi, pela API JSON do site (`/++api++/`). |
| Grau + turno (`opcoes`) | ✅ | Grau pelo título ("Licenciatura em…") ou pela "Titulação"; 1 curso sem grau no site recebe o do Censo. |
| Modalidade | ✅ | Todos `presencial`. |
| Duração em semestres | 🟡 | 115 de 121 (anos, semestres ou "períodos" da ficha). |
| Turno | 🟡 | 113 de 121; texto livre do site ("Manhã e Tarde", "Tarde/Noite"…). |
| `sobre` | ✅ | 119 de 121 ("Sobre o Curso" ou texto inicial; "Perfil do egresso" junto, como na UEM). |
| `mercadoTrabalho` | ✅ | 107 de 121 (seção "Atuação" e variações). |
| Casamento com códigos e-MEC | 🟡 | 114 diretos + 3 preenchidos à mão (nome diferente no Censo); 4 sem par. |

**Pendências da UTFPR:**

- [ ] 4 cursos sem par no Censo 2024 (provavelmente novos): Arquitetura e Urbanismo (Guarapuava), Engenharia de Produção (Curitiba), Engenharia Mecatrônica (Ponta Grossa), Sistemas de Informação (Londrina).
- [ ] Sisu: 105 de 107 linhas casam. Sobram 1690306 (Engenharia de Produção, Curitiba, Integral) e 102667 (Design, Curitiba).
- [ ] Bacharelado em Química Ambiental (Curitiba): a página do curso responde 401 (não é pública); entra só com nome, grau e link.

### 1.4. UFSC: Universidade Federal de Santa Catarina (e-MEC 585, `--ies ufsc`) 🟡

| Item | Estado | Observação |
|---|---|---|
| Lista de cursos: nome, cidade/UF, link (`urlOrigem`) | ✅ | 92 cursos em 5 campi, da tabela de https://guiadecursos.ufsc.br/listagem/. Os EaD ficam numa página à parte e ficam de fora. |
| Grau (`opcoes`) | 🟡 | 42 de 92 pelo nome ou título ("Matemática – Licenciatura", "Química (Licenciatura, Bacharelado e Tecnológica)") e engenharias/arquitetura = bacharelado; os outros recebem o grau do Censo pelo casamento. |
| Turno | ➖ | O guia não informa: fica `null`. |
| Modalidade | ✅ | Todos `presencial`. |
| Duração em semestres | ➖ | O guia não informa: fica `null`. |
| `sobre` | ✅ | 92 de 92: texto da página até o separador dos depoimentos (depoimentos com nome de estudante ficam de fora, LGPD). |
| `mercadoTrabalho` | ➖ | Sem seção própria (o assunto aparece no meio do texto corrido): fica `null`. |
| Casamento com códigos e-MEC | 🟡 | `spiders/dados/ufsc_codigos.csv`: 70 diretos + 15 páginas com bacharelado e licenciatura (31 linhas, confirmadas) + 4 preenchidos à mão (candidato único no Censo); 3 sem par. |

**Pendências da UFSC:**

- [ ] 3 cursos sem par: Ciência de Dados (Florianópolis) e Medicina (Curitibanos), sem código no Censo 2024 (provavelmente novos); Letras – Português (Florianópolis), com 2 candidatos no Censo (bacharelado 351945 e licenciatura 51945), deixado sem par pela regra do candidato único.
- [ ] Preenchidos à mão (conferir): Ciências da Computação → 14217 "Ciência da Computação"; Engenharia de Produção Plena → 1608913 "Engenharia de Produção"; Engenharia de Transportes e Logística (Joinville) → 1270311; Licenciatura Indígena → 1156456 "Licenciatura Intercultural Indígena".

### 1.5. UFSM: Universidade Federal de Santa Maria (e-MEC 582, `--ies ufsm`) 🟡

| Item | Estado | Observação |
|---|---|---|
| Lista de cursos: nome, cidade/UF, link (`urlOrigem`) | ✅ | 97 cursos em 4 campi, pelas linhas `Sitemap:` do https://www.ufsm.br/robots.txt (o site não tem uma página com a lista). Os EaD (`educacao-a-distancia`) ficam de fora. |
| Grau + turno (`opcoes`) | 🟡 | 88 de 97, pelo texto-modelo "Apresentação" (grau, modalidade, turno e períodos de cada habilitação); uma opção por grau ("Diurno ou Noturno"). O bloco "Núcleo Comum" (ABI) fica de fora. 9 páginas não têm o bloco: o grau vem do Censo quando há casamento. |
| Modalidade | 🟡 | 88 de 97 (`presencial`); `null` nas 9 páginas sem o bloco. |
| Duração em semestres | 🟡 | 81 de 97 ("8 períodos semestrais" → 8). 7 cursos têm durações diferentes por habilitação: o texto lista cada uma e `duracaoSemestres` fica vazio, como na UEL. |
| `sobre` | 🟡 | 38 de 97: só da página "Sobre o curso" (`…/sobre-o-curso/`); 59 cursos não têm essa página (404). |
| `mercadoTrabalho` | 🟡 | 16 de 97: seção "Áreas de atuação" (e variações) da página "Sobre o curso". |
| Casamento com códigos e-MEC | 🟡 | `spiders/dados/ufsm_codigos.csv`: 65 diretos + 18 páginas com mais de um código no Censo (turno ou grau; 39 linhas, confirmadas) + 5 preenchidos à mão (candidato único); 9 sem par. |

**Pendências da UFSM:**

- [ ] `sobre` só para 38 cursos. Os outros sites de curso usam páginas com nomes diferentes no menu ("Descrição do Curso", "Sobre"…); seguir o link do menu é a próxima melhoria (a página "Sobre" = `informacoes-gerais` cita coordenação pelo nome e não serve).
- [ ] 9 sem par: Ciência de Dados e IA (Cachoeira do Sul), Direito (Frederico Westphalen), Nanotecnologia e Inovação Computacional, Segurança Cibernética, Licenciatura Intercultural Indígena e Licenciatura Interdisciplinar Indígena (Frederico Westphalen) e Mbya Guarani (Santa Maria), sem código no Censo 2024; Letras e "Química Industrial e Química Bacharelado" (Santa Maria), com mais de um candidato.
- [ ] Preenchidos à mão (conferir): Engenharia de Computação → 121624; Produção Editorial → 1107232; Publicidade e Propaganda → 40152; Relações Públicas (Santa Maria) → 40153; Programa Especial de Graduação → 1113371 (formação de professores para a educação profissional).
- [ ] "Programa Especial de Graduação" (3 semestres, licenciatura) entrou como curso porque está na lista de graduação do site; confirmar se deve aparecer.

---

### 1.6. O que cada IES entrega

**Obrigatório para contar como "completa"** (quando o site tem o dado):

- Lista de cursos: nome, campus/cidade/UF e link da página (`urlOrigem`)
- Grau + turno (`opcoes`, uma opção por grau)
- Modalidade
- Duração em semestres (`duracaoSemestres`, mantendo `duracaoTexto`)
- `sobre` (texto do curso)
- `mercadoTrabalho` (quando a página tiver a seção)
- Casamento com os códigos e-MEC (`spiders/dados/<chave>_codigos.csv` revisado)

**Opcional:**

- [ ] Formas de ingresso (vestibular próprio, SISU, transferência…)
- [ ] Vestibular próprio (datas e edital), quando o calendário for definido (P-33)
- [ ] Nota de corte própria (vestibular)
- [ ] Disciplinas (texto do site, D-41)
- [ ] Mensalidade (**só privadas**)

---

## 2. Scrapers gerais (uma fonte nacional, vale para todas as IES)

| # | Fonte | Para quê | Estado | Observação |
|---|---|---|---|---|
| G1 | **Censo da Educação Superior (INEP)** | Instituição (nome, sigla, tipo, cidade/UF); vagas, gratuidade e área Cine de cada curso | ✅ | `uv run sauf-scraper censo`. Só IES com spider registrado (D-43). |
| G2 | **IGC / nota MEC** (INEP) | "Nota MEC" nos cards e no filtro de universidades | ✅ | `uv run sauf-scraper igc --arquivo fontes/IGC_2023.xlsx`. Faixa 1 a 5 por ano; 'SC' vira null (D-48, D-49). |
| G3 | **SISU: notas de corte** | Nota de corte nos cards, no detalhe, nos favoritos e nos cursos parecidos | ✅ | `uv run sauf-scraper sisu --arquivo fontes/<planilha do Sisu>.xlsx`. Sisu 2025, só **ampla concorrência**; corte 0 vira null (D-50, D-53). |
| G4 | **PROUni / FIES** | "Aceita PROUni/FIES" | 🚫 Fora do plano | As 5 IES são públicas (D-51). |
| G5 | **e-MEC: endereço** | "Onde fica" na página da universidade | 🚫 Fora do plano | O endereço já vem no arquivo de IES do Censo (`DS_ENDERECO_IES` etc.), estendendo o G1 na fase C (D-51). |
| G6 | **RAIS / CAGED** | Aba "Mercado e salários" | ⏸️ | Fora do MVP (P-31 a → D-40). |
| G7 | **Questões do ENEM** (maritaca-ai/enem + `ITENS_PROVA` do INEP) | Banco de questões dos simulados | ✅ | `uv run sauf-scraper questoes enem --ano 2022 2023 2024`. 540 questões, 42 pendentes de revisão (ADR-SC-010, D-68 da API). Rotas de simulado e front: depois. |

---

## 3. Não é scraper (cadastro manual)

| Item | Onde aparece | Estado |
|---|---|---|
| Logo, foto de capa, "sobre", site e ano de fundação da IES | Lista e página da universidade, favoritos | ✅ `dados/ies/<sigla>.toml` + `uv run sauf-scraper ies` (TR-343; passo a passo em [dados/README.md](../dados/README.md); D-98 a D-103 da API, ADR-BE-017) |
| Imagem dos cursos (uma por área Cine) | Cards e página dos cursos | ✅ `dados/areas.toml` + `uv run sauf-scraper areas` (D-101). A tela de cursos do front ainda não mostra (vai ser refeita) |
| Conteúdo das formas de ingresso (PROUni, SISU, FIES, ENEM) | Tela "Formas de ingresso" | ❌ |
| Eventos e calendário | Calendário e notificações | ⏸️ Adiado (P-33) |

**Enviado ao Supabase em 20/11/2026 (Carlos):** migration do TR-343, ano, "sobre" e site das 5 IES, logo e capa da UEM e logo da UEL. Detalhes em [dados/README.md](../dados/README.md), seção 7.

### 3.1. Imagens escolhidas e ainda não baixadas (TR-343)

O servidor de arquivos do Wikimedia (upload.wikimedia.org) bloqueia programas sem contato no
User-Agent (HTTP 429 desde 20/11/2026); o navegador não é bloqueado. Para baixar à mão: abrir a
página, clicar em **Baixar** (Download) e escolher o tamanho indicado; salvar no destino com o
nome exato. Logo: PNG com cerca de 500 px de largura (o Commons gera o PNG do SVG); capa e área:
cerca de 1280 px de largura, JPG. Licença e autor já conferidos na API do Commons em 20/11/2026.
Depois: trocar o comentário `# [...] pendente` do TOML pela seção completa (dados/README.md,
seções 4 e 5), `--dry-run`, enviar e riscar a linha.

| Destino | Baixar | Página no Commons | Licença | Autor | Crédito obrigatório |
|---|---|---|---|---|---|
| `dados/ies/img/uel-capa.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:Londrina_-_UEL.jpg | CC BY 2.0 | Luís Guilherme Fernandes Pereira | sim |
| `dados/ies/img/utfpr-logo.png` | PNG ~500 px | https://commons.wikimedia.org/wiki/File:UTFPR_logo.svg | CC BY 4.0 | Universidade Tecnológica Federal do Paraná | sim |
| `dados/ies/img/utfpr-capa.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:C%C3%A2mpus_Curitiba.jpg | CC BY 2.0 | UTFPR em Imagens | sim |
| `dados/ies/img/ufsc-logo.png` | PNG ~500 px | https://commons.wikimedia.org/wiki/File:Brasao_UFSC_vertical_extenso.svg | Public domain | Universidade Federal de Santa Catarina | não |
| `dados/ies/img/ufsc-capa.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:Pr%C3%A9dio_da_Reitoria_-_Universidade_Federal_de_Santa_Catarina_(UFSC).JPG | CC BY-SA 4.0 | Airtonjordani | sim |
| `dados/ies/img/ufsm-logo.jpg` | JPG ~500 px | https://commons.wikimedia.org/wiki/File:Brasao_UFSM_Color_300dpi.jpg | Public domain | Universidade Federal de Santa Maria | não |
| `dados/ies/img/ufsm-capa.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:Entrada_da_UFSM.jpg | CC BY-SA 3.0 | Imagens SM | sim |
| `dados/areas/img/00-programas-basicos.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:Lecture_Room_Stairs_(Unsplash).jpg | CC0 | Markus Birner | não |
| `dados/areas/img/01-educacao.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:Students_learning_together_(Unsplash).jpg | CC0 | Alexis Brown | não |
| `dados/areas/img/02-artes-e-humanidades.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:Old_books_on_bookshelf._(Unsplash).jpg | CC0 | Clem Onojeghuo | não |
| `dados/areas/img/03-ciencias-sociais.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:Microphone_(Unsplash).jpg | CC0 | Kai Oberhäuser | não |
| `dados/areas/img/04-negocios.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:Working_in_open_office_space_(Unsplash).jpg | CC0 | Crew crew | não |
| `dados/areas/img/05-ciencias-naturais.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:Plants_in_beakers_(Unsplash).jpg | CC0 | chuttersnap chuttersnap | não |
| `dados/areas/img/06-computacao.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:Code_on_computer_monitor_(Unsplash).jpg | CC0 | Markus Spiske | não |
| `dados/areas/img/07-engenharia.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:View_Above_Construction_Site_(Unsplash).jpg | CC0 | chuttersnap chuttersnap | não |
| `dados/areas/img/08-agricultura.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:Farm_Field_(Unsplash).jpg | CC0 | Arkadiusz Zet | não |
| `dados/areas/img/09-saude.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:Stethoscope_No.120.JPG | CC0 | Tama998 | não |
| `dados/areas/img/10-servicos.jpg` | JPG ~1280 px | https://commons.wikimedia.org/wiki/File:Michael_(Unsplash).jpg | CC0 | Toa Heftiba | não |

---

## 4. Definição de pronto: spider novo

- [ ] Está registrado em `spiders/__init__.py` e aparece no `uv run sauf-scraper --listar`.
- [ ] Testes do parser com fixture sem dados pessoais; `pytest` e `ruff check` passam.
- [ ] Não coleta dados pessoais (ex.: seção de coordenação).
- [ ] `casar` rodado e CSV revisado (`ambiguo`/`sem_par` resolvidos ou listados aqui).
- [ ] `--dry-run` conferido: campos obrigatórios da seção 1.4, textos sem HTML e `urlOrigem` em todos.
- [ ] Testado contra a API local (`censo` → spider) sem `rejeitados`.
- [ ] Regra nova registrada no `DECISOES.md` e este checklist atualizado.
