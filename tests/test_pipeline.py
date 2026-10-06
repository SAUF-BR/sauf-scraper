from sauf_scraper.client.http import HttpEducado
from sauf_scraper.core.models import Curso
from sauf_scraper.core.pipeline import executar
from sauf_scraper.spiders.base import Spider


class DestinoFalso:
    def __init__(self):
        self.lotes = []

    def enviar(self, lote):
        self.lotes.append(lote)


def spider_que_devolve(lote_fixo, chave_spider):
    class SpiderOk(Spider):
        chave = chave_spider

        def coletar(self):
            return lote_fixo

    return SpiderOk


class SpiderQueQuebra(Spider):
    chave = "quebrado"

    def coletar(self):
        raise RuntimeError("site fora do ar")


class SpiderComDadoInvalido(Spider):
    chave = "invalido"

    def coletar(self):
        Curso(chave="x", url_origem="https://x.br", nome="")  # nome vazio -> ValidationError


def test_falha_em_um_spider_nao_derruba_os_outros(settings, lote):
    destino = DestinoFalso()
    spiders = [SpiderQueQuebra, SpiderComDadoInvalido, spider_que_devolve(lote, "ok")]

    resumo = executar(spiders, HttpEducado(settings), destino, execucao_id="t1")

    assert [r.sucesso for r in resumo.resultados] == [False, False, True]
    assert resumo.resultados[0].erro == "RuntimeError: site fora do ar"
    assert resumo.resultados[1].erro.startswith("validação")
    assert len(destino.lotes) == 1
    assert resumo.houve_falha
