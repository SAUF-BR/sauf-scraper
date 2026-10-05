import pytest
import responses

from sauf_scraper.client.http import BloqueadoPorRobotsError, HttpEducado


@responses.activate
def test_respeita_robots_txt(settings):
    responses.get("https://site.br/robots.txt", body="User-agent: *\nDisallow: /privado/")
    responses.get("https://site.br/publico/cursos", body="ok")

    http = HttpEducado(settings)

    assert http.get("https://site.br/publico/cursos").text == "ok"
    with pytest.raises(BloqueadoPorRobotsError):
        http.get("https://site.br/privado/x")


@responses.activate
def test_sem_robots_txt_libera_tudo(settings):
    responses.get("https://site.br/robots.txt", status=404)
    responses.get("https://site.br/cursos", body="ok")

    assert HttpEducado(settings).get("https://site.br/cursos").text == "ok"


@responses.activate
def test_envia_user_agent_do_bot(settings):
    responses.get("https://site.br/robots.txt", status=404)
    responses.get("https://site.br/cursos", body="ok")

    HttpEducado(settings).get("https://site.br/cursos")

    assert responses.calls[-1].request.headers["User-Agent"] == settings.user_agent
