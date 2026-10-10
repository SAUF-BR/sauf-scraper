"""Testes do parser e do spider da UEM, usando o HTML real salvo em tests/fixtures/uem/.

uv run pytest tests/test_parser_uem.py -v
"""

from pathlib import Path

import pytest

from sauf_scraper.core.models import Grau, Modalidade, Opcao
from sauf_scraper.parsers.uem import (
    CursoListado,
    DetalhesCurso,
    extrair_detalhes,
    extrair_lista,
    separar_mercado,
    turnos_por_grau,
)
from sauf_scraper.spiders.uem import (
    cidade_do_campus,
    graus_da_habilitacao,
    montar_curso,
    opcoes_da_pagina,
    uf_do_campus,
)

FIXTURES = Path(__file__).parent / "fixtures" / "uem"


def ler(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


# --- Lista de cursos ---------------------------------------------------------------


def test_lista_traz_todos_os_cursos_presenciais():
    assert len(extrair_lista(ler("lista.html"))) == 67


def test_primeiro_curso_da_lista():
    primeiro = extrair_lista(ler("lista.html"))[0]
    assert primeiro.nome == "Administração"
    assert primeiro.campus == "Campus Sede - Maringá/PR"
    assert primeiro.url == (
        "https://www.pen.uem.br/site/public/curso/c6e9c1b9daea38a42b28d6d97f567ce6d551aeb0"
    )


def test_curso_de_outro_campus_sai_com_o_campus_certo():
    cursos = extrair_lista(ler("lista.html"))
    cianorte = [c for c in cursos if c.campus.startswith("Campus Regional de Cianorte")]
    assert [c.nome for c in cianorte] == ["Ciências Contábeis", "Design", "Moda", "Pedagogia"]


def test_link_do_ead_fica_de_fora():
    cursos = extrair_lista(ler("lista.html"))
    assert all("/curso/" in c.url for c in cursos)


# --- Página do curso ---------------------------------------------------------------


def test_detalhes_de_engenharia_de_software():
    detalhes = extrair_detalhes(ler("curso_engenharia_software.html"))
    assert detalhes.turno == "Noturno"
    assert detalhes.habilitacao == "Bacharelado"
    assert detalhes.prazo_minimo == "5 anos"
    assert detalhes.prazo_maximo == "9 anos"


def test_detalhes_com_rotulos_em_b_em_vez_de_strong():
    # Arquitetura e Urbanismo usa <b>Turno:</b> no lugar de <strong>Turno:</strong>.
    detalhes = extrair_detalhes(ler("curso_arquitetura_urbanismo.html"))
    assert detalhes.turno == "integral"
    assert detalhes.habilitacao == "Bacharelado"
    assert detalhes.prazo_minimo == "5 anos"
    assert detalhes.prazo_maximo == "9 anos"


@pytest.mark.parametrize(
    "arquivo", ["curso_engenharia_software.html", "curso_arquitetura_urbanismo.html"]
)
def test_dados_da_coordenacao_nao_sao_coletados(arquivo):
    # LGPD: nome e e-mail de professores não entram no SAUF.
    texto = str(extrair_detalhes(ler(arquivo)))
    assert "Fulano" not in texto
    assert "coordenador@" not in texto


@pytest.mark.parametrize(
    ("habilitacao", "turno", "esperado"),
    [
        (
            "Licenciatura (Integral ou Noturno) ou Bacharelado (Integral)",
            "Integral ou Noturno",
            {"licenciatura": "Integral ou Noturno", "bacharelado": "Integral"},
        ),
        (
            "Licenciatura (noturno) ou Bacharelado (vespertino / noturno)",
            None,
            {"licenciatura": "Noturno", "bacharelado": "Vespertino/Noturno"},
        ),
        (
            "Licenciatura em Química (Noturno) e Bacharelado em Química (Integral)",
            "Noturno e Integral.",
            {"licenciatura": "Noturno", "bacharelado": "Integral"},
        ),
        (
            "Licenciatura ou Bacharelado",
            "Noturno (Licenciatura) ou Vespertino/Noturno (Bacharelado)",
            {"licenciatura": "Noturno", "bacharelado": "Vespertino/Noturno"},
        ),
        ("Bacharelado e/ou Licenciatura", "Noturno", {}),
        (None, None, {}),
    ],
)
def test_turnos_por_grau(habilitacao, turno, esperado):
    assert turnos_por_grau(habilitacao, turno) == esperado


def test_rotulos_em_maiusculas_e_no_plural():
    html = (
        "<p><strong>TURNOS:</strong> Noturno e Integral.<br/>"
        "<strong>HABILITAÇÃO :</strong> Licenciatura em Química (Noturno) e Bacharelado</p>"
    )
    detalhes = extrair_detalhes(html)
    assert detalhes.turno == "Noturno e Integral."
    assert detalhes.habilitacao.startswith("Licenciatura em Química")


def test_dois_pontos_fora_do_rotulo():
    detalhes = extrair_detalhes("<p><b>Turno</b>: Noturno<br/><b>Habilitação</b>:Bacharelado</p>")
    assert detalhes.turno == "Noturno"
    assert detalhes.habilitacao == "Bacharelado"


def test_pagina_sem_os_campos_devolve_none():
    detalhes = extrair_detalhes("<html><body><p>Nada aqui</p></body></html>")
    assert detalhes.turno is None
    assert detalhes.habilitacao is None
    assert detalhes.sobre is None
    assert detalhes.mercado_trabalho is None


# --- Seção "Sobre o Curso" ---------------------------------------------------------


def test_sobre_o_curso_para_antes_de_mercado_de_trabalho():
    # Na página de Eng. de Software, "Mercado de Trabalho" fica no mesmo <p> do texto.
    sobre = extrair_detalhes(ler("curso_engenharia_software.html")).sobre

    assert sobre.startswith(
        "O objetivo principal do curso de Bacharelado em Engenharia de Software"
    )
    assert sobre.endswith("para o trabalho coletivo e interdisciplinar.")
    assert "Mercado de Trabalho" not in sobre
    assert "Sobre o Curso" not in sobre


def test_sobre_o_curso_com_rotulo_em_b_para_antes_de_mais_informacoes():
    # Na página de Arquitetura o rótulo é <b> e o "Mercado de trabalho" vem sem negrito.
    sobre = extrair_detalhes(ler("curso_arquitetura_urbanismo.html")).sobre

    assert sobre.startswith("O ensino de graduação em Arquitetura e Urbanismo")
    assert "Mais informações" not in sobre
    assert "Projeto Pedagógico" not in sobre


@pytest.mark.parametrize(
    "arquivo", ["curso_engenharia_software.html", "curso_arquitetura_urbanismo.html"]
)
def test_sobre_o_curso_e_texto_puro_com_quebras_de_linha(arquivo):
    sobre = extrair_detalhes(ler(arquivo)).sobre

    assert "<" not in sobre and "&nbsp;" not in sobre and "\xa0" not in sobre
    assert "\n- Formar profissionais" in sobre or "\n- A qualidade de vida" in sobre
    assert all(linha == linha.strip() and "  " not in linha for linha in sobre.split("\n"))
    assert "Fulano" not in sobre and "coordenador@" not in sobre


def test_sobre_o_curso_separa_paragrafos_com_linha_em_branco():
    html = """<div><p><strong>Sobre o Curso:</strong></p>
        <p>Primeiro parágrafo
           com quebra no código-fonte.<br/>Linha seguinte.</p>
        <p>Segundo parágrafo.</p>
        <p><b>Mercado de Trabalho</b> Não entra.</p></div>"""

    assert extrair_detalhes(html).sobre == (
        "Primeiro parágrafo com quebra no código-fonte.\nLinha seguinte.\n\nSegundo parágrafo."
    )


# --- Seção "Mercado de Trabalho" ----------------------------------------------------


def test_mercado_de_trabalho_para_antes_de_mais_informacoes():
    mercado = extrair_detalhes(ler("curso_engenharia_software.html")).mercado_trabalho

    assert mercado.startswith("O curso de graduação em Engenharia de Software forma profissionais")
    assert mercado.endswith("tanto no Brasil quanto no exterior.")
    assert "Mais informações" not in mercado
    assert "Projeto Pedagógico" not in mercado
    assert "Mercado de Trabalho" not in mercado


def test_mercado_de_trabalho_nao_traz_dados_da_coordenacao():
    mercado = extrair_detalhes(ler("curso_engenharia_software.html")).mercado_trabalho

    assert "Fulano" not in mercado and "coordenador@" not in mercado
    assert "<" not in mercado and " " not in mercado


def test_mercado_de_trabalho_sem_negrito_na_pagina_de_arquitetura():
    detalhes = extrair_detalhes(ler("curso_arquitetura_urbanismo.html"))

    assert detalhes.mercado_trabalho.startswith("De acordo com o Conselho de Arquitetura")
    assert "Mercado de trabalho" not in detalhes.sobre
    assert "Mais informações" not in detalhes.mercado_trabalho


def test_pagina_sem_mercado_de_trabalho_devolve_none():
    html = "<div><p><strong>Sobre o Curso:</strong><br/>Só o texto do curso.</p></div>"
    detalhes = extrair_detalhes(html)

    assert detalhes.sobre == "Só o texto do curso."
    assert detalhes.mercado_trabalho is None


def test_mercado_de_trabalho_para_antes_da_coordenacao():
    html = """<div><p><b>Mercado de Trabalho</b><br/>Atua em empresas.</p>
        <p><b>Coordenação</b></p><p>Coordenador: Fulano - fulano@exemplo.br</p></div>"""

    assert extrair_detalhes(html).mercado_trabalho == "Atua em empresas."


def test_mercado_de_trabalho_sem_negrito_sai_do_sobre():
    # Trecho real de Administração na UEM, encurtado: o título é texto puro no <p>.
    html = """<div><p><strong>Sobre o Curso:</strong><br/>Forma administradores.</p>
        <p style="text-align:justify">&nbsp;</p>
        <p style="text-align:justify">Mercado de trabalho<br/>
        No contexto atual, o administrador é altamente demandado.</p>
        <p>&nbsp;</p><p><strong>Mais informações:</strong>&nbsp;</p>
        <p><a href="x.pdf">Projeto Pedagógico do Curso</a></p></div>"""

    detalhes = extrair_detalhes(html)

    assert detalhes.sobre == "Forma administradores."
    assert detalhes.mercado_trabalho == "No contexto atual, o administrador é altamente demandado."


def test_titulo_de_mercado_na_mesma_quebra_de_linha_do_sobre():
    # Arquitetura: o título vem logo depois de um <br/>, sem parágrafo novo.
    sobre, mercado = separar_mercado("Primeiro.\nMercado de trabalho\nAtua no CAU.")

    assert (sobre, mercado) == ("Primeiro.", ["Atua no CAU."])


def test_frase_que_comeca_com_mercado_de_trabalho_nao_e_titulo():
    texto = "O mercado de trabalho do economista é amplo.\nMercado de trabalho em alta."

    assert separar_mercado(texto) == (texto, [])


# --- "Campo de atuação" também é mercado de trabalho --------------------------------


def test_campo_de_atuacao_sem_negrito_vira_mercado():
    # Trecho real de Tecnologia em Gastronomia na UEM, encurtado.
    html = """<div><p><strong>Sobre o Curso:</strong></p>
        <p>O Tecnólogo em Gastronomia pode atuar na prestação de serviços de alimentação.</p>
        <p>Campo de Atuação:</p>
        <p>O profissional pode atuar em restaurantes de hotéis e cruzeiros.</p>
        <p><strong>Mais informações:</strong></p></div>"""

    detalhes = extrair_detalhes(html)

    assert detalhes.sobre == (
        "O Tecnólogo em Gastronomia pode atuar na prestação de serviços de alimentação."
    )
    assert (
        detalhes.mercado_trabalho
        == "O profissional pode atuar em restaurantes de hotéis e cruzeiros."
    )


@pytest.mark.parametrize("titulo", ["CAMPO DE ATUAÇÃO", "Campo de atuacao", "Campo de Atuação :"])
def test_campo_de_atuacao_em_maiusculas_ou_sem_acento(titulo):
    # Eng. de Produção (Goioerê) usa o título todo em maiúsculas.
    sobre, mercado = separar_mercado(f"Forma engenheiros.\n{titulo}\nIndústrias e serviços.")

    assert (sobre, mercado) == ("Forma engenheiros.", ["Indústrias e serviços."])


def test_campo_de_atuacao_em_negrito_vira_mercado():
    html = """<div><p><strong>Sobre o Curso:</strong> Forma biomédicos.</p>
        <p><b>Campo de Atuação</b><br/>Laboratórios clínicos.</p>
        <p><b>Coordenação</b></p><p>Coordenador: Fulano - fulano@exemplo.br</p></div>"""

    detalhes = extrair_detalhes(html)

    assert detalhes.sobre == "Forma biomédicos."
    assert detalhes.mercado_trabalho == "Laboratórios clínicos."


def test_frase_com_campo_de_atuacao_nao_e_cortada():
    # Física Médica: a frase começa com "O campo de atuação" e não é título.
    texto = "O campo de atuação de um Físico Médico é bastante amplo.\nHospitais e clínicas."

    assert separar_mercado(texto) == (texto, [])


def test_pagina_com_as_duas_secoes_junta_na_ordem():
    html = """<div><p><strong>Sobre o Curso:</strong><br/>Forma profissionais.</p>
        <p>Campo de atuação<br/>Indústria e serviços.</p>
        <p>Perfil do egresso<br/>Generalista.</p>
        <p><b>Mercado de Trabalho</b><br/>Alta demanda no Paraná.</p>
        <p><strong>Mais informações:</strong></p></div>"""

    detalhes = extrair_detalhes(html)

    assert detalhes.sobre == "Forma profissionais.\n\nPerfil do egresso\nGeneralista."
    assert detalhes.mercado_trabalho == "Indústria e serviços.\n\nAlta demanda no Paraná."


# --- Montagem do Curso -------------------------------------------------------------


def test_montar_curso_de_engenharia_de_software():
    item = CursoListado(
        nome="Engenharia de Software",
        campus="Campus Sede - Maringá/PR",
        url="https://www.pen.uem.br/site/public/curso/a99a3305e6ffbd5db96ef5506978504214b31397",
    )
    curso = montar_curso(item, extrair_detalhes(ler("curso_engenharia_software.html")))

    assert curso.chave == "uem:engenharia-de-software:maringa:noturno"
    assert str(curso.url_origem) == item.url
    assert curso.opcoes == [Opcao(grau=Grau.BACHARELADO, turno="Noturno")]
    assert curso.duracao_texto == "5 anos"
    assert curso.duracao_semestres == 10
    assert curso.turno == "Noturno"
    assert curso.modalidade == Modalidade.PRESENCIAL
    assert (curso.cidade, curso.uf) == ("Maringá", "PR")
    assert curso.codigos_emec == []
    assert curso.sobre.startswith("O objetivo principal do curso")
    assert curso.mercado_trabalho.startswith("O curso de graduação em Engenharia de Software")


@pytest.mark.parametrize(
    ("campus", "cidade"),
    [
        ("Campus Sede - Maringá/PR", "Maringá"),
        ("Campus do Arenito - Cidade Gaúcha/PR", "Cidade Gaúcha"),
        ("Câmpus Regional do Vale do Ivaí - Ivaiporã/PR", "Ivaiporã"),
    ],
)
def test_cidade_do_campus(campus, cidade):
    assert cidade_do_campus(campus) == cidade


@pytest.mark.parametrize(
    ("campus", "uf"),
    [("Campus Sede - Maringá/PR", "PR"), ("Campus Sede - Maringá", None), ("x/Paraná", None)],
)
def test_uf_do_campus(campus, uf):
    assert uf_do_campus(campus) == uf


@pytest.mark.parametrize(
    ("habilitacao", "graus"),
    [
        ("Bacharelado", [Grau.BACHARELADO]),
        ("Licenciatura", [Grau.LICENCIATURA]),
        ("Bacharelado e/ou Licenciatura", [Grau.BACHARELADO, Grau.LICENCIATURA]),
        (
            "Licenciatura (Integral ou Noturno) ou Bacharelado (Integral)",
            [Grau.LICENCIATURA, Grau.BACHARELADO],
        ),
        ("Tecnologia", [Grau.TECNOLOGICO]),
        ("Nutricionista", []),
        ("", []),
        (None, []),
    ],
)
def test_graus_da_habilitacao(habilitacao, graus):
    assert graus_da_habilitacao(habilitacao) == graus


def test_opcoes_trazem_o_turno_de_cada_grau():
    detalhes = DetalhesCurso(
        turno="Integral ou Noturno",
        habilitacao="Licenciatura (Integral ou Noturno) ou Bacharelado (Integral)",
    )
    assert opcoes_da_pagina(detalhes) == [
        Opcao(grau=Grau.LICENCIATURA, turno="Integral ou Noturno"),
        Opcao(grau=Grau.BACHARELADO, turno="Integral"),
    ]


def test_opcoes_sem_turno_por_grau_usam_o_turno_da_pagina():
    detalhes = DetalhesCurso(turno="Noturno", habilitacao="Bacharelado e/ou Licenciatura")
    assert {o.turno for o in opcoes_da_pagina(detalhes)} == {"Noturno"}
