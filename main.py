"""Backend do explorador de discografia.

Dados: API pública do Deezer (artistas, álbuns, capas e faixas). Não precisa de chave nem de cadastro.
As capas vêm direto do CDN do Deezer e são carregadas pelo navegador.

Rodar: uvicorn main:app --reload
"""
import asyncio
import re
import time
import unicodedata
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi import Path as ParamPath
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

DEEZER_URL = "https://api.deezer.com"
MAX_ALBUNS = 600  # teto de segurança para artistas com catálogo enorme
PASTA_STATIC = Path(__file__).parent / "static"
ID_NUMERICO = r"^\d{1,12}$"

_cliente: httpx.AsyncClient | None = None
_vagas = asyncio.Semaphore(4)  # no máximo 4 pedidos ao mesmo tempo; o Deezer limita o ritmo


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    global _cliente
    _cliente = httpx.AsyncClient(headers={"Accept": "application/json"}, timeout=15)
    yield
    await _cliente.aclose()


app = FastAPI(title="álbuns · discografia", lifespan=ciclo_de_vida)


class Cache:
    """Cache em memória com validade. Zera quando o servidor reinicia."""

    def __init__(self, limite: int = 500):
        self._dados: dict = {}
        self._limite = limite

    def get(self, chave):
        item = self._dados.get(chave)
        if not item:
            return None
        validade, valor = item
        if validade < time.monotonic():
            del self._dados[chave]
            return None
        return valor

    def set(self, chave, valor, segundos: int):
        if len(self._dados) >= self._limite:
            self._dados.pop(next(iter(self._dados)))
        self._dados[chave] = (time.monotonic() + segundos, valor)


cache = Cache()


async def deezer_get(caminho: str, params: dict | None = None, nao_achou: str = "Não encontrei isso no Deezer.") -> dict:
    """GET na API do Deezer. O Deezer às vezes responde 200 com {"error": {...}} no corpo."""
    async with _vagas:
        try:
            r = await _cliente.get(f"{DEEZER_URL}{caminho}", params=params)
        except httpx.HTTPError:
            raise HTTPException(502, "Não consegui falar com o Deezer.")

    if r.status_code != 200:
        raise HTTPException(502, f"O Deezer respondeu com erro ({r.status_code}).")
    try:
        corpo = r.json()
    except ValueError:
        raise HTTPException(502, "O Deezer enviou uma resposta que não entendi.")

    erro = corpo.get("error") if isinstance(corpo, dict) else None
    if erro:
        codigo = erro.get("code") if isinstance(erro, dict) else None
        tipo = erro.get("type") if isinstance(erro, dict) else None
        if codigo in (4, 100):
            raise HTTPException(503, "O Deezer pediu para esperar um pouco. Tente de novo em instantes.")
        if codigo == 800 or tipo == "DataException":
            raise HTTPException(404, nao_achou)
        raise HTTPException(502, "O Deezer não conseguiu responder agora.")
    return corpo


# ---------- limpeza dos dados ----------

def https_ou_none(url) -> str | None:
    return url if isinstance(url, str) and url.startswith("https://") else None


def link_deezer(url) -> str | None:
    """Só aceita links do próprio Deezer (o endereço vira um <a href> na página)."""
    try:
        host = urlparse(url).hostname or ""
        if urlparse(url).scheme == "https" and (host == "deezer.com" or host.endswith(".deezer.com")):
            return url
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def link_previa(url) -> str | None:
    """Trecho de 30 s da faixa (vai para um <audio>): só https e só do CDN do Deezer."""
    try:
        p = urlparse(url)
        host = p.hostname or ""
        if p.scheme == "https" and (host.endswith(".dzcdn.net") or host.endswith(".deezer.com")):
            return url
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def url_capa(g: dict, campo: str) -> str | None:
    """Capa do Deezer; álbuns sem arte vêm com o endereço vazio ou com md5 vazio."""
    if "md5_image" in g and not g["md5_image"]:
        return None
    url = https_ou_none(g.get(campo))
    if not url or "/cover//" in url:
        return None
    return url


def formatar_artista(a: dict) -> dict:
    return {
        "id": a["id"],
        "nome": a.get("name", ""),
        "foto": https_ou_none(a.get("picture_medium") or a.get("picture")),
        "foto_grande": https_ou_none(a.get("picture_big") or a.get("picture_xl") or a.get("picture_medium")),
        "albuns": a.get("nb_album"),
        "fas": a.get("nb_fan"),
    }


# Trechos de título que só indicam outra edição do mesmo disco
EDICAO = re.compile(
    r"\b(deluxe|expanded|remaster(?:ed)?|remasteriz\w*|anniversary|anivers[aá]rio|bonus|b[oô]nus"
    r"|edition|edi[cç][aã]o|collector'?s?|special|explicit|clean)\b",
    re.I,
)
ENTRE_PARENTESES = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
AO_VIVO = re.compile(
    r"(?:[\(\[]|\s-\s)[^\)\]]*\blive\b"          # "(Live at ...)", "[Live]", "- Live"
    r"|^live\s+(?:at|in|from|@)\b"                # "Live at Leeds"
    r"|\b(?:ao vivo|en vivo|en directo|unplugged|in concert)\b",
    re.I,
)
COLETANEA = re.compile(
    r"\b(?:greatest hits|best of|the very best|anthology|essentials|the collection|"
    r"cole[tâ]nea|o melhor de|as melhores|grandes sucessos|the singles)\b",
    re.I,
)


def sem_edicao(titulo: str) -> str:
    """Tira "(Deluxe)", "[Remastered 2011]" e "- Expanded Edition" do título.
    Deixa de fora de propósito "(Taylor's Version)" e "(Live)", que são outros discos."""
    t = ENTRE_PARENTESES.sub(lambda m: "" if EDICAO.search(m.group(0)) else m.group(0), titulo)
    partes = t.split(" - ")
    if len(partes) > 1 and EDICAO.search(partes[-1]):
        t = " - ".join(partes[:-1])
    return t.strip() or titulo.strip()


def chave_titulo(titulo: str) -> str:
    t = unicodedata.normalize("NFKD", sem_edicao(titulo))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[\W_]+", "", t) or titulo.lower()


def classificar(g: dict, titulo: str) -> str:
    tipo = (g.get("record_type") or "album").lower()
    if tipo == "single":
        return "single"
    if tipo == "ep":
        return "ep"
    if tipo.startswith("compile") or COLETANEA.search(titulo):
        return "coletanea"
    if AO_VIVO.search(titulo):
        return "ao-vivo"
    return "album"


def ler_data(g: dict) -> tuple[str | None, int | None]:
    d = (g.get("release_date") or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) or int(d[:4]) < 1900:
        return None, None
    return d, int(d[:4])


def formatar_lancamento(g: dict) -> dict | None:
    if "id" not in g or not g.get("title"):
        return None
    titulo = g["title"].strip()
    data, ano = ler_data(g)
    capa = url_capa(g, "cover_medium") or url_capa(g, "cover")
    return {
        "id": g["id"],
        "titulo": titulo,
        "data": data,
        "ano": ano,
        "tipo": classificar(g, titulo),
        "capa": capa,
        "capa2x": url_capa(g, "cover_big") or capa,
        "explicito": bool(g.get("explicit_lyrics")),
    }


def juntar_edicoes(itens: list[dict]) -> list[dict]:
    """O Deezer lista o mesmo disco várias vezes (original, deluxe, remasterizado, outras regiões).
    Fica uma entrada por disco: a versão original."""
    por_chave: dict[tuple, list[dict]] = {}
    for it in itens:
        por_chave.setdefault((it["tipo"], chave_titulo(it["titulo"])), []).append(it)

    saida: list[dict] = []
    for lista in por_chave.values():
        bases = [i for i in lista if sem_edicao(i["titulo"]) == i["titulo"].strip()]
        if not bases:
            # só existem versões especiais: fica a mais antiga, com o título limpo
            antiga = min(lista, key=lambda i: (i["data"] or "9999", len(i["titulo"])))
            saida.append({**antiga, "titulo": sem_edicao(antiga["titulo"])})
            continue

        bases.sort(key=lambda i: i["data"] or "9999")
        mantidas: list[dict] = []
        for b in bases:
            anterior = mantidas[-1] if mantidas else None
            mesmo_disco = anterior is not None and (
                (b["ano"] is None and anterior["ano"] is None)
                or (b["ano"] is not None and anterior["ano"] is not None and abs(b["ano"] - anterior["ano"]) <= 1)
            )
            if not mesmo_disco:
                mantidas.append(b)
            elif not anterior["capa"] and b["capa"]:
                anterior["capa"], anterior["capa2x"] = b["capa"], b["capa2x"]
        saida.extend(mantidas)
    return saida


async def buscar_albuns(artista_id: str) -> list[dict]:
    """Todos os lançamentos do artista, 100 por página."""
    todos: list[dict] = []
    indice = 0
    while indice < MAX_ALBUNS:
        try:
            pagina = await deezer_get(f"/artist/{artista_id}/albums", {"limit": 100, "index": indice})
        except HTTPException as e:
            if e.status_code == 404 and indice > 0:
                break  # acabou antes do esperado
            raise
        lote = pagina.get("data") or []
        todos += lote
        indice += 100
        total = pagina.get("total")
        if not lote or (total is not None and indice >= total) or (total is None and not pagina.get("next")):
            break
    return todos


# ---------- rotas ----------

@app.get("/api/artistas")
async def buscar_artistas(q: str = Query(..., min_length=2, max_length=100)):
    termo = q.strip()
    chave = ("busca", termo.lower())
    if (guardado := cache.get(chave)) is not None:
        return guardado

    dados = await deezer_get("/search/artist", {"q": termo, "limit": 8})
    resultado = [formatar_artista(a) for a in dados.get("data", []) if "id" in a]
    cache.set(chave, resultado, 3600)
    return resultado


@app.get("/api/artistas/{artista_id}")
async def discografia(artista_id: str = ParamPath(..., pattern=ID_NUMERICO)):
    chave = ("disco", artista_id)
    if (guardado := cache.get(chave)) is not None:
        return guardado

    artista, brutos = await asyncio.gather(
        deezer_get(f"/artist/{artista_id}", nao_achou="Artista não encontrado."),
        buscar_albuns(artista_id),
    )

    itens = [i for i in (formatar_lancamento(g) for g in brutos) if i]
    lancamentos = juntar_edicoes(itens)
    lancamentos.sort(key=lambda l: (l["data"] or "9999-99-99", l["titulo"].lower()))

    resultado = {
        "artista": formatar_artista(artista),
        "lancamentos": lancamentos,
        "contagens": dict(Counter(l["tipo"] for l in lancamentos)),
    }
    cache.set(chave, resultado, 86400)
    return resultado


@app.get("/api/albuns/{album_id}")
async def detalhe_album(album_id: str = ParamPath(..., pattern=ID_NUMERICO)):
    chave = ("album", album_id)
    if (guardado := cache.get(chave)) is not None:
        return guardado

    album, faixas = await asyncio.gather(
        deezer_get(f"/album/{album_id}", nao_achou="Álbum não encontrado."),
        deezer_get(f"/album/{album_id}/tracks", {"limit": 200}, nao_achou="Álbum não encontrado."),
    )

    lista = [
        {
            "n": i,
            "titulo": f.get("title") or "",
            "duracao": f.get("duration"),
            "explicito": bool(f.get("explicit_lyrics")),
            "previa": link_previa(f.get("preview")),
        }
        for i, f in enumerate(faixas.get("data") or [], start=1)
    ]
    resultado = {
        "id": album.get("id"),
        "titulo": album.get("title") or "",
        "artista": (album.get("artist") or {}).get("name"),
        "data": ler_data(album)[0],
        "generos": [g["name"] for g in (album.get("genres") or {}).get("data", []) if g.get("name")],
        "gravadora": album.get("label") or None,
        "duracao": album.get("duration"),
        "num_faixas": album.get("nb_tracks") or len(lista),
        "link": link_deezer(album.get("link")),
        "faixas": lista,
    }
    cache.set(chave, resultado, 86400)
    return resultado


@app.get("/api/destaques")
async def destaques():
    """Álbuns em alta no Deezer, um por artista, para a vitrine da tela inicial."""
    chave = ("destaques",)
    if (guardado := cache.get(chave)) is not None:
        return guardado

    dados = await deezer_get("/chart/0/albums", {"limit": 60})
    vistos, itens = set(), []
    for g in dados.get("data") or []:
        artista = g.get("artist") or {}
        capa = url_capa(g, "cover_medium")
        if not capa or "id" not in g or "id" not in artista or artista["id"] in vistos:
            continue
        vistos.add(artista["id"])
        itens.append({
            "id": g["id"],
            "titulo": g.get("title") or "",
            "artista_id": artista["id"],
            "artista": artista.get("name") or "",
            "capa": capa,
            "capa2x": url_capa(g, "cover_big"),
        })
    cache.set(chave, itens[:36], 6 * 3600)
    return itens[:36]


@app.get("/artista/{artista_id}", include_in_schema=False)
async def pagina_do_artista(artista_id: str = ParamPath(..., pattern=ID_NUMERICO)):
    """Link compartilhável: devolve a mesma página e o app.js abre o artista."""
    return FileResponse(PASTA_STATIC / "index.html")


# Precisa vir depois das rotas da API
app.mount("/", StaticFiles(directory=PASTA_STATIC, html=True), name="static")
