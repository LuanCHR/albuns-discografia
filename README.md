# álbuns · discografia

Explorador de discografias. Busque um artista ou banda e veja todos os álbuns numa parede de capas organizada por década, com filtros por tipo, ordem crescente ou decrescente e uma ficha completa (faixas, duração, gravadora) ao clicar numa capa.

- **Dados e capas:** [Deezer](https://developers.deezer.com/api) (API pública, sem chave e sem login). Muito mais rápida e completa que o MusicBrainz.
- **Tela inicial viva:** fileiras de capas dos álbuns em alta no Deezer; clicar numa capa abre o artista.
- **Prévia de 30 segundos** de cada faixa na ficha do álbum, e o fundo da ficha ganha o tom da capa.
- **Link por artista:** `/artista/230` abre direto, e o botão "Copiar link" e o voltar do navegador funcionam.
- **Números da carreira** (anos de carreira, intervalo médio entre álbuns, década mais produtiva) e modo "Capas pequenas" para catálogos grandes.
- **Só álbuns por padrão**, com filtros para EPs, singles, ao vivo e coletâneas.
- **Edições repetidas somem:** "Deluxe", "Remastered", "Expanded Edition" etc. são juntadas ao álbum original. Regravações como "(Taylor's Version)" continuam, porque são outro disco.
- **Sem capa:** o título vira a arte do álbum.
- **Muitos álbuns:** capas agrupadas por década, com o número da década acompanhando a rolagem.
- **Backend:** Python + FastAPI + httpx, com cache em memória e limite de requisições simultâneas.
- **Frontend:** HTML, CSS e JavaScript puros, sem build, com a identidade do álbuns (logo, Bricolage Grotesque, cores).

## Como rodar

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Abra http://127.0.0.1:8000. Não precisa de variável de ambiente nem de chave.

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

Usam respostas falsas do Deezer, então rodam sem internet.

## Estrutura

```
main.py           API (busca, discografia, detalhe do álbum, cache)
test_api.py       testes da API
static/
  index.html      página
  style.css       visual (identidade nas variáveis do topo)
  app.js          busca, filtros, parede por década, ficha do álbum
  logo.svg        wordmark "álbuns" em vetor
  favicon.svg     o "á" como ícone da aba
  fonts/          Bricolage Grotesque + licença
```

## API

| Rota | O que faz |
|---|---|
| `GET /api/artistas?q=nome` | busca artistas |
| `GET /api/artistas/{id}` | lançamentos do artista (ordenados por data, sem edições repetidas) e contagem por tipo |
| `GET /api/albuns/{id}` | detalhe do álbum com lista de faixas e prévias |
| `GET /api/destaques` | álbuns em alta (um por artista), usados na tela inicial |
| `GET /artista/{id}` | a mesma página, para links diretos |

Para conferir o que o Deezer devolve para um artista, abra `http://127.0.0.1:8000/api/artistas?q=nome` no navegador.

## Ideias para evoluir

- Comparar dois artistas lado a lado
- Link compartilhável para cada artista
- Hospedar online
