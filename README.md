# Eventos da Vida — gestor/planeador de eventos (concertos, cultura, viagens)

App Flask + SQLite para:
- Rever/aceitar/rejeitar eventos recomendados (concertos, exposições, viagens).
- Aprender os teus gostos a partir dos aceites/rejeitados (pesos por tag).
- Verificar regras pessoais (ex: 1 viagem fora de Lisboa a cada 2 semanas, 1 concerto/mês, 1 visita cultural/mês).
- Expor uma API para um cron externo alimentar eventos e consultar o estado das regras.

## Estrutura
- `app.py` — aplicação Flask (rotas UI + API)
- `schema.sql` — esquema SQLite
- `rules_default.json` — regras por defeito (editáveis na tabela `rules`)
- `templates/`, `static/` — dashboard
- `wsgi_pythonanywhere_com.py` — modelo de configuração WSGI para PythonAnywhere

## Variáveis de ambiente
- `EVENTOS_DB_PATH` — caminho do ficheiro SQLite (default: `eventos.db` na pasta da app)
- `EVENTOS_API_KEY` — chave usada no header `X-API-Key` para os endpoints `/api/*`

## Correr localmente
```
python -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt
EVENTOS_API_KEY=minha-chave ./venv/Scripts/python.exe app.py
```
Abre http://127.0.0.1:5000

## Deploy na PythonAnywhere (free tier)

1. Consola **Bash** na PythonAnywhere:
   ```
   git clone https://github.com/paulodiasfaria/eventos-app.git
   cd eventos-app
   python3.10 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ```
2. Separador **Web** → **Add a new web app** → escolhe **Manual configuration** → Python 3.10.
3. Em **Code**:
   - Source code: `/home/paulodiasfaria/eventos-app`
   - Working directory: `/home/paulodiasfaria/eventos-app`
   - WSGI configuration file: edita o ficheiro e cola o conteúdo de `wsgi_pythonanywhere_com.py` (ajusta a `EVENTOS_API_KEY` para uma chave secreta tua).
4. Em **Virtualenv**: aponta para `/home/paulodiasfaria/eventos-app/venv`
5. Clica **Reload**.
6. A app fica em `https://paulodiasfaria.pythonanywhere.com`

### Atualizar depois de alterações
```
cd ~/eventos-app
git pull
./venv/bin/pip install -r requirements.txt   # só se requirements mudou
```
Depois recarrega a app no separador Web (botão Reload).

## API (usada pelo cron do Hermes)
Header obrigatório em todos os `/api/*`: `X-API-Key: <EVENTOS_API_KEY>`

- `POST /api/events` — body: lista de eventos (ou um só objeto)
  ```json
  [{"title":"...", "category":"concert|cultural|trip|other", "city":"...", "country":"...",
    "venue":"...", "date_options":["YYYY-MM-DD"], "tags":["tag1","tag2"],
    "source_url":"...", "price":"...", "notes":"..."}]
  ```
- `GET /api/rules/status` — estado de cada regra (ok / at_risk / overdue)
- `GET /api/recommendations/top?limit=3` — top eventos pendentes por score
