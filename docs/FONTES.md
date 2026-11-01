# Fontes de dados

Regra: todo link acessado pelo projeto (avaliação, spider, importador) entra aqui, com a data do
primeiro acesso.

Quem acessar um link novo atualiza esta página no mesmo commit ou PR (ver
[CONTRIBUTING.md](../CONTRIBUTING.md)). Atualizado em 01/11/2026.

## Fontes gerais

| Fonte | Link | O que usamos | Arquivo/ano | Primeiro acesso |
|---|---|---|---|---|
| Censo da Educação Superior (INEP), microdados | https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-da-educacao-superior | `sauf-scraper censo`: instituição (nome, sigla, tipo, cidade/UF, endereço da sede) e cursos (área Cine, vagas, gratuidade); casamento site × código e-MEC | `MICRODADOS_ED_SUP_IES_2024.CSV` e `MICRODADOS_CADASTRO_CURSOS_2024.CSV` (Censo 2024), .zip baixado à mão e extraído em `fontes/microdados_censo_da_educacao_superior_2024/` (qualquer pasta `fontes/microdados_censo*` serve; vale a de maior ano) | 10/2026 |
| IGC – Índice Geral de Cursos (INEP) | https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/indicadores-de-qualidade-da-educacao-superior (aba 2023) | `sauf-scraper igc`: nota MEC da instituição (D-49) | `IGC_2023.xlsx`, em `fontes/` | 16/10/2026 |
| Sisu – Inscrições e notas de corte (MEC) | https://www.gov.br/mec/pt-br/sisu/documentos (seção "Inscrições e notas de corte") | `sauf-scraper sisu`: nota de corte, só ampla concorrência (D-50) | `portal-sisu-sisu-2025-inscricoes-e-notas-de-corte.xlsx` (Sisu 2025), em `fontes/` | 16/10/2026 |
| Cadastro e-MEC | https://emec.mec.gov.br/ | Avaliado; fora do plano (D-51), o endereço veio do Censo | — | 10/2026 |

O link do Censo é a página oficial de download do INEP; o arquivo foi baixado à mão.

## Universidades

| Universidade (e-MEC) | Situação | Primeiro link acessado | Fontes usadas pelo spider/avaliação | Data |
|---|---|---|---|---|
| UEM (57) | Selecionada, spider pronto | https://www.pen.uem.br/site/public/cursos | Lista: https://www.pen.uem.br/site/public/cursos · Curso: `https://www.pen.uem.br/site/public/curso/<id>` · https://www.pen.uem.br/robots.txt | 10/2026 |
| UEL (9) | Selecionada, spider pronto | https://portal.uel.br/ | Lista: https://sites.uel.br/prograd/cursos-de-graduacao-da-uel/ (via https://sites.uel.br/prograd/graduacao/) · Curso: `https://graduacao.uel.br/<slug>/` · subpágina avaliada: https://graduacao.uel.br/administracao/projeto-pedagogico-ppc/ · robots.txt: não existe (404) | 28/10/2026 |
| UTFPR (588) | Selecionada, spider pronto | https://www.utfpr.edu.br/cursos/graduacao | API: https://www.utfpr.edu.br/++api++/cursos/coordenacoes/graduacao/@search?path.depth=2&b_size=1000 · Curso: `https://www.utfpr.edu.br/++api++/cursos/coordenacoes/graduacao/<campus>/<curso>/apresentacao` (link público sem `/++api++`) · https://www.utfpr.edu.br/robots.txt | 29/10/2026 |
| UFSC (585) | Selecionada | https://ufsc.br/ | Lista: https://guiadecursos.ufsc.br/listagem/ · Curso: `https://guiadecursos.ufsc.br/<curso>/` · robots.txt: não existe (404) | 28/10/2026 |
| UFSM (582) | Selecionada | https://www.ufsm.br/cursos/graduacao | Lista: sitemaps em https://www.ufsm.br/robots.txt · Curso: `https://www.ufsm.br/cursos/graduacao/<campus>/<curso>/` e `…/sobre-o-curso` | 29/10/2026 |
| UFPR (571) | Reserva (versão reduzida) | https://ufpr.br/ | `https://ufpr.br/cursos-em-<campus>/` (Curitiba, Jandaia do Sul, Matinhos, Palotina, Pontal do Paraná, Toledo) · sites de curso amostrados: https://sociaisaplicadas.ufpr.br/administracao/, http://www.mat.ufpr.br/graduacao/matematica/ (404), https://palotina.ufpr.br/graduacao/agronomia/ · https://ufpr.br/gradeecorpodocente/ · vestibular: https://servicos.nc.ufpr.br/PortalNC/Concurso?concurso=PS2027 e o guia (PortalNC/obterDocumento?pub=9378) · robots: https://ufpr.br/robots.txt | 28/10/2026 |
| USP (55) | Reserva | https://www5.usp.br/ | https://www5.usp.br/ensino/graduacao/ · https://seucursousp.prg.usp.br/ · JupiterWeb: https://uspdigital.usp.br/jupiterweb/jupColegiadoLista?tipo=N, `jupCursoLista?codcg=<unidade>&tipo=N`, `listarGradeCurricular?codcg=…&codcur=…&codhab=…&tipo=N`, `jupCarreira.jsp` · robots: https://www5.usp.br/robots.txt | 28/10/2026 |
| Unicamp (54) | Descartada (robots proíbe) | https://www.unicamp.br/ | https://www.unicamp.br/graduacao/ · https://www.comvest.unicamp.br/cursos (robots: `Disallow: /`) · https://www.dac.unicamp.br/portal/graduacao/cursos e …/catalogos-de-cursos (catálogo em `/sistemas/`, proibido) · robots: unicamp.br, comvest.unicamp.br e dac.unicamp.br | 29/10/2026 |
| Unesp (56) | Descartada (só JavaScript) | https://www2.unesp.br/ | https://vestibular.unesp.br/ e https://vestibular.unesp.br/cursos-por-area/ · robots: https://www2.unesp.br/robots.txt e https://vestibular.unesp.br/robots.txt | 29/10/2026 |
| Unespar (18492) | Reserva (versão reduzida) | https://unespar.edu.br/ | Lista: https://prograd.unespar.edu.br/informacoes/cursos-graduacao · cursos amostrados: https://apucarana.unespar.edu.br/graduacao/administracao, https://paranavai.unespar.edu.br/graduacao/cursos/ciencias-biologicas, https://uniaodavitoria.unespar.edu.br/ensino/graduacao/arquitetura · robots: unespar.edu.br e prograd.unespar.edu.br | 29/10/2026 |
