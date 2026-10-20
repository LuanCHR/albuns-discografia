"""Testes da API com respostas falsas do Deezer (não fazem requisições reais)."""
import asyncio

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main

ARTISTA = "230"


@pytest.fixture(autouse=True)
def limpar_cache():
    main.cache._dados.clear()


def falso_deezer(respostas):
    """Cria um deezer_get falso: devolve a resposta registrada para cada caminho."""
    chamadas = []

    async def deezer_get(caminho, params=None, **_):
        chamadas.append((caminho, params))
        return respostas[caminho]

    deezer_get.chamadas = chamadas
    return deezer_get


def disco(id_, titulo, data, tipo="album", md5="abc123", explicito=False):
    capa = f"https://cdn-images.dzcdn.net/images/cover/{md5}/%s-000000-80-0-0.jpg"
    return {
        "id": id_, "title": titulo, "release_date": data, "record_type": tipo,
        "md5_image": md5, "explicit_lyrics": explicito,
        "cover_medium": capa % "250x250", "cover_big": capa % "500x500",
    }


def discografia(monkeypatch, discos, total=None):
    monkeypatch.setattr(main, "deezer_get", falso_deezer({
        f"/artist/{ARTISTA}": {"id": 230, "name": "Banda"},
        f"/artist/{ARTISTA}/albums": {"data": discos, "total": total if total is not None else len(discos)},
    }))
    with TestClient(main.app) as c:
        return c.get(f"/api/artistas/{ARTISTA}").json()


# ---------- busca ----------

def test_busca_formata_artistas(monkeypatch):
    falso = falso_deezer({"/search/artist": {"data": [{
        "id": 230, "name": "Kanye West", "nb_album": 50, "nb_fan": 1000,
        "picture_medium": "https://cdn-images.dzcdn.net/images/artist/x/250x250.jpg",
        "picture_big": "https://cdn-images.dzcdn.net/images/artist/x/500x500.jpg",
    }]}})
    monkeypatch.setattr(main, "deezer_get", falso)

    with TestClient(main.app) as c:
        r = c.get("/api/artistas", params={"q": "kanye"})

    assert r.status_code == 200
    assert r.json() == [{
        "id": 230, "nome": "Kanye West", "albuns": 50, "fas": 1000,
        "foto": "https://cdn-images.dzcdn.net/images/artist/x/250x250.jpg",
        "foto_grande": "https://cdn-images.dzcdn.net/images/artist/x/500x500.jpg",
    }]
    assert falso.chamadas[0][1]["q"] == "kanye"


def test_busca_ignora_foto_que_nao_e_https(monkeypatch):
    monkeypatch.setattr(main, "deezer_get", falso_deezer(
        {"/search/artist": {"data": [{"id": 1, "name": "X", "picture_medium": "javascript:alert(1)"}]}}))
    with TestClient(main.app) as c:
        assert c.get("/api/artistas", params={"q": "xx"}).json()[0]["foto"] is None


def test_busca_exige_dois_caracteres():
    with TestClient(main.app) as c:
        assert c.get("/api/artistas", params={"q": "a"}).status_code == 422


# ---------- discografia ----------

def test_tipos_ordem_e_contagens(monkeypatch):
    corpo = discografia(monkeypatch, [
        disco(3, "Terceiro", "1999-05-21"),
        disco(1, "Primeiro", "1991-01-01"),
        disco(2, "Ao Vivo no Rio (Live)", "1995-03-01"),
        disco(4, "Greatest Hits", "1997-04-04"),
        disco(5, "Um EP", "1993-02-02", tipo="ep"),
        disco(6, "Hit", "1992-02-02", tipo="single"),
        disco(9, "Mistério", "0000-00-00"),
    ])

    assert [(l["titulo"], l["tipo"]) for l in corpo["lancamentos"]] == [
        ("Primeiro", "album"), ("Hit", "single"), ("Um EP", "ep"), ("Ao Vivo no Rio (Live)", "ao-vivo"),
        ("Greatest Hits", "coletanea"), ("Terceiro", "album"), ("Mistério", "album"),
    ]
    assert corpo["lancamentos"][-1]["ano"] is None and corpo["lancamentos"][-1]["data"] is None
    assert corpo["contagens"] == {"album": 3, "single": 1, "ep": 1, "ao-vivo": 1, "coletanea": 1}
    assert corpo["artista"]["nome"] == "Banda"


def test_edicoes_repetidas_somem_mas_outro_disco_com_mesmo_nome_fica(monkeypatch):
    corpo = discografia(monkeypatch, [
        disco(1, "Fearless", "2008-11-11"),
        disco(2, "Fearless (Platinum Edition)", "2009-10-27"),
        disco(3, "Fearless (Taylor's Version)", "2021-04-09"),     # regravação: é outro disco
        disco(4, "Abbey Road", "1969-09-26"),
        disco(5, "Abbey Road (Remastered 2019)", "2019-09-27"),
        disco(6, "Nevermind - Deluxe Edition", "2011-09-27"),
        disco(7, "Nevermind", "1991-09-24"),
    ])

    titulos = [(l["titulo"], l["ano"]) for l in corpo["lancamentos"]]
    assert titulos == [
        ("Abbey Road", 1969), ("Nevermind", 1991), ("Fearless", 2008), ("Fearless (Taylor's Version)", 2021),
    ]


def test_so_versao_especial_fica_com_titulo_limpo(monkeypatch):
    corpo = discografia(monkeypatch, [
        disco(1, "Rumours (Deluxe)", "2013-01-29"),
        disco(2, "Rumours [Expanded Edition]", "2004-03-30"),
    ])
    assert [(l["titulo"], l["ano"]) for l in corpo["lancamentos"]] == [("Rumours", 2004)]


def test_live_no_nome_do_disco_nao_vira_ao_vivo(monkeypatch):
    corpo = discografia(monkeypatch, [
        disco(1, "Live Through This", "1994-04-12"),
        disco(2, "Alive 2007", "2007-06-19"),
        disco(3, "Live at Leeds", "1970-05-16"),
        disco(4, "Acústico (Ao Vivo)", "2001-01-01"),
    ])
    tipos = {l["titulo"]: l["tipo"] for l in corpo["lancamentos"]}
    assert tipos == {
        "Live Through This": "album", "Alive 2007": "album",
        "Live at Leeds": "ao-vivo", "Acústico (Ao Vivo)": "ao-vivo",
    }


def test_duplicata_exata_mantem_a_que_tem_capa(monkeypatch):
    corpo = discografia(monkeypatch, [
        disco(1, "Disco", "2000-01-01", md5=""),
        disco(2, "Disco", "2000-06-01", md5="abc"),
    ])
    assert [l["id"] for l in corpo["lancamentos"]] == [1]
    assert corpo["lancamentos"][0]["capa"] is not None


def test_sem_capa_vira_none_e_capa2x_acompanha(monkeypatch):
    corpo = discografia(monkeypatch, [
        disco(1, "Sem arte", "2000-01-01", md5=""),
        disco(2, "Com arte", "2001-01-01", explicito=True),
    ])
    sem, com = corpo["lancamentos"]
    assert sem["capa"] is None and sem["capa2x"] is None
    assert com["capa"].endswith("250x250-000000-80-0-0.jpg") and "500x500" in com["capa2x"]
    assert com["explicito"] is True and sem["explicito"] is False


def test_usa_cache(monkeypatch):
    falso = falso_deezer({
        f"/artist/{ARTISTA}": {"id": 230, "name": "Banda"},
        f"/artist/{ARTISTA}/albums": {"data": [disco(1, "Disco", "2000-01-01")], "total": 1},
    })
    monkeypatch.setattr(main, "deezer_get", falso)

    with TestClient(main.app) as c:
        c.get(f"/api/artistas/{ARTISTA}")
        c.get(f"/api/artistas/{ARTISTA}")

    assert len(falso.chamadas) == 2  # artista + 1 página, só na primeira vez


def test_pagina_resultados(monkeypatch):
    indices = []

    async def deezer_get(caminho, params=None, **_):
        if caminho == f"/artist/{ARTISTA}":
            return {"id": 230, "name": "Prolífico"}
        indices.append(params["index"])
        ini = params["index"]
        return {"data": [disco(i, f"Disco {i}", "2000-01-01") for i in range(ini, min(ini + 100, 230))], "total": 230}

    monkeypatch.setattr(main, "deezer_get", deezer_get)
    with TestClient(main.app) as c:
        corpo = c.get(f"/api/artistas/{ARTISTA}").json()

    assert indices == [0, 100, 200]
    assert len(corpo["lancamentos"]) == 230


def test_ids_invalidos():
    with TestClient(main.app) as c:
        assert c.get("/api/artistas/nao-e-numero").status_code == 422
        assert c.get("/api/albuns/1x").status_code == 422


# ---------- detalhe do álbum ----------

def test_detalhe_do_album(monkeypatch):
    monkeypatch.setattr(main, "deezer_get", falso_deezer({
        "/album/10": {
            "id": 10, "title": "Graduation", "release_date": "2007-09-11", "label": "Roc-A-Fella",
            "duration": 3100, "nb_tracks": 2, "link": "https://www.deezer.com/album/10",
            "artist": {"name": "Kanye West"}, "genres": {"data": [{"name": "Rap/Hip Hop"}]},
        },
        "/album/10/tracks": {"data": [
            {"title": "Good Morning", "duration": 195, "explicit_lyrics": False},
            {"title": "Champion", "duration": 168, "explicit_lyrics": True},
        ]},
    }))
    with TestClient(main.app) as c:
        corpo = c.get("/api/albuns/10").json()

    assert corpo["titulo"] == "Graduation" and corpo["artista"] == "Kanye West"
    assert corpo["generos"] == ["Rap/Hip Hop"] and corpo["gravadora"] == "Roc-A-Fella"
    assert corpo["faixas"] == [
        {"n": 1, "titulo": "Good Morning", "duracao": 195, "explicito": False, "previa": None},
        {"n": 2, "titulo": "Champion", "duracao": 168, "explicito": True, "previa": None},
    ]
    assert corpo["link"] == "https://www.deezer.com/album/10"


def test_link_so_aceita_deezer():
    assert main.link_deezer("https://www.deezer.com/album/1") == "https://www.deezer.com/album/1"
    assert main.link_deezer("https://evil.example/album/1") is None
    assert main.link_deezer("https://deezer.com.evil.example/x") is None
    assert main.link_deezer("javascript:alert(1)") is None
    assert main.link_deezer(None) is None


def test_previa_so_aceita_cdn_do_deezer():
    ok = "https://cdnt-preview.dzcdn.net/api/1/1/a.mp3"
    assert main.link_previa(ok) == ok
    assert main.link_previa("https://evil.example/a.mp3") is None
    assert main.link_previa("http://cdnt-preview.dzcdn.net/a.mp3") is None
    assert main.link_previa(None) is None


def test_destaques_um_por_artista_e_sem_capa_some(monkeypatch):
    def g(i, art, md5="x"):
        return {"id": i, "title": f"A{i}", "md5_image": md5, "artist": {"id": art, "name": f"Art{art}"},
                "cover_medium": f"https://cdn-images.dzcdn.net/images/cover/{i}/250x250.jpg",
                "cover_big": f"https://cdn-images.dzcdn.net/images/cover/{i}/500x500.jpg"}
    monkeypatch.setattr(main, "deezer_get", falso_deezer({"/chart/0/albums": {"data": [
        g(1, 10), g(2, 10), g(3, 11, md5=""), g(4, 12)]}}))
    with TestClient(main.app) as c:
        corpo = c.get("/api/destaques").json()
    assert [x["id"] for x in corpo] == [1, 4]
    assert corpo[0]["artista_id"] == 10


def test_pagina_do_artista_serve_o_index():
    with TestClient(main.app) as c:
        r = c.get("/artista/230")
        assert r.status_code == 200 and "<html" in r.text
        assert c.get("/artista/abc").status_code == 422


# ---------- erros do Deezer ----------

def chamar_deezer(corpo, status=200):
    def resposta(_):
        return httpx.Response(status, json=corpo)

    async def rodar():
        main._cliente = httpx.AsyncClient(transport=httpx.MockTransport(resposta))
        try:
            return await main.deezer_get("/artist/1")
        finally:
            await main._cliente.aclose()

    return asyncio.run(rodar())


def test_erros_do_deezer_viram_mensagens_claras():
    assert chamar_deezer({"id": 1}) == {"id": 1}

    with pytest.raises(HTTPException) as e:
        chamar_deezer({"error": {"type": "DataException", "message": "no data", "code": 800}})
    assert e.value.status_code == 404

    with pytest.raises(HTTPException) as e:
        chamar_deezer({"error": {"type": "Exception", "message": "Quota limit exceeded", "code": 4}})
    assert e.value.status_code == 503

    with pytest.raises(HTTPException) as e:
        chamar_deezer({}, status=500)
    assert e.value.status_code == 502
