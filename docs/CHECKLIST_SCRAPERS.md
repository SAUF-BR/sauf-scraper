# Checklist dos scrapers

O que já existe, o que falta e o que cada scraper precisa entregar para as telas do
protótipo. Base: análise "protótipo × dados" (09/10/2026) e as decisões D-38 a D-47 do
`sauf-api/docs/DECISOES.md`. Como criar um spider: [CONTRIBUTING.md](../CONTRIBUTING.md).

Legenda: ✅ feito · 🟡 parcial / com pendência · ❌ falta · ⏸️ adiado ou fora do MVP · ➖ não se aplica

Atualizado em 10/10/2026.

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

### 1.2. Scraper de mais 4 universidades (a definir) ❌

IES ainda **a definir**. Cada uma precisa entregar:

**Obrigatório para contar como "completa":**

- [ ] Lista de cursos: nome, campus/cidade/UF e link da página (`urlOrigem`)
- [ ] Grau + turno (`opcoes`)
- [ ] Modalidade
- [ ] Duração em semestres (`duracaoSemestres`, mantendo `duracaoTexto`)
- [ ] `sobre` (texto do curso)
- [ ] `mercadoTrabalho` (quando a página tiver a seção)
- [ ] Casamento com os códigos e-MEC (`spiders/dados/<chave>_codigos.csv` revisado)

**Opcional:**

- [ ] Formas de ingresso (vestibular próprio, SISU, transferência…)
- [ ] Vestibular próprio (datas e edital), quando o calendário for definido (P-33)
- [ ] Nota de corte própria (vestibular)
- [ ] Disciplinas (texto do site, D-41)
- [ ] Mensalidade (**só privadas**)

| # | IES | e-MEC | Chave | Estado |
|---|---|---|---|---|
| 2 | a definir | — | — | ❌ |
| 3 | a definir | — | — | ❌ |
| 4 | a definir | — | — | ❌ |
| 5 | a definir | — | — | ❌ |

---

## 2. Scrapers gerais (uma fonte nacional, vale para todas as IES)

| # | Fonte | Para quê | Estado | Observação |
|---|---|---|---|---|
| G1 | **Censo da Educação Superior (INEP)** | Instituição (nome, sigla, tipo, cidade/UF); vagas, gratuidade e área Cine de cada curso | ✅ | `uv run sauf-scraper censo`. Só IES com spider registrado (D-43). |
| G2 | **IGC / nota MEC** (e-MEC/INEP) | "Nota MEC" nos cards e no filtro de universidades | ❌ | |
| G3 | **SISU: notas de corte** | Nota de corte nos cards, no detalhe, nos favoritos e nos cursos parecidos | ❌ | Prioridade. Aguardando a planilha (xlsx) do MEC que o Carlos vai baixar. Só **ampla concorrência** (P-37 a → D-45). |
| G4 | **PROUni / FIES** | "Aceita PROUni/FIES" nos favoritos e nas formas de ingresso | ❌ | Baixa prioridade. |
| G5 | **e-MEC: endereço** | "Onde fica" na página da universidade | ❌ | |
| G6 | **RAIS / CAGED** | Aba "Mercado e salários" | ⏸️ | Fora do MVP (P-31 a → D-40). |

---

## 3. Não é scraper (cadastro manual)

| Item | Onde aparece | Estado |
|---|---|---|
| Logo, foto e "sobre" da IES (e ano de fundação) | Lista e página da universidade | ❌ (forma de cadastro a definir) |
| Conteúdo das formas de ingresso (PROUni, SISU, FIES, ENEM) | Tela "Formas de ingresso" | ❌ |
| Eventos e calendário | Calendário e notificações | ⏸️ Adiado (P-33) |

---

## 4. Definição de pronto: spider novo

Um spider só conta como pronto quando:

- [ ] Está registrado em `spiders/__init__.py` e aparece no `uv run sauf-scraper --listar`.
- [ ] Tem testes do parser com fixture (`tests/fixtures/<chave>/`, sem dados pessoais) e
      trechos de regressão para os casos estranhos do site.
- [ ] `uv run pytest` e `uv run ruff check .` passam.
- [ ] Não coleta dados pessoais (ex.: seção de coordenação).
- [ ] Casamento com o Censo feito: `casar --ies <chave>` rodado e o CSV revisado à mão
      (linhas `ambiguo` e `sem_par` resolvidas ou listadas como pendência neste checklist).
- [ ] `--dry-run` conferido: `output/emec-<código>.json` com os campos obrigatórios da
      seção 1.2, sem HTML nos textos e com `urlOrigem` em todos os cursos.
- [ ] Testado contra a API local (`censo` → spider) sem `rejeitados`.
- [ ] Regra nova de negócio (se houver) registrada no `sauf-api/docs/DECISOES.md`.
- [ ] Este checklist atualizado com o estado da IES.
