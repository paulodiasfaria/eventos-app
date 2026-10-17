"""
Eventos App - gestor/planeador de eventos de vida (concertos, visitas culturais, viagens).

Arquitetura:
- Flask + SQLite (ficheiro local, funciona em free tiers como PythonAnywhere).
- Eventos candidatos entram via API (POST /api/events), tipicamente alimentados
  por um cron job externo (Hermes) que usa web search para encontrar eventos.
- O utilizador aceita/rejeita candidatos no dashboard -> isso ajusta os pesos
  de preferencia por tag (aprendizagem simples).
- Motor de regras verifica se cumpres as regras definidas (ex: 1 concerto/mes).
- API /api/rules/status e /api/recommendations/top para um cron de WhatsApp consultar.
- Scoring considera tags aprendidas, distancia a Lisboa (mais perto = melhor),
  preco (gratis = melhor) e horario (noite = pior, por causa da Lara, 3 anos).
- Eventos que ja ocorreram sao filtrados automaticamente. Eventos marcados para
  o proprio dia de hoje só interessam se forem em Lisboa ou a <=50km.
"""
import json
import os
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta

from flask import Flask, g, jsonify, redirect, render_template, request, url_for

DB_PATH = os.environ.get("EVENTOS_DB_PATH", os.path.join(os.path.dirname(__file__), "eventos.db"))
API_KEY = os.environ.get("EVENTOS_API_KEY", "changeme-dev-key")
TODAY_RADIUS_KM = 50  # eventos no dia de hoje só interessam dentro deste raio (ou em Lisboa)

app = Flask(__name__)

# Distancias aproximadas (km por estrada) de cidades/concelhos comuns a Lisboa.
# Usado como fallback quando o cron nao fornece distance_km explicitamente.
CITY_DISTANCE_KM = {
    "lisboa": 0, "lisbon": 0,
    "amadora": 10, "odivelas": 12, "oeiras": 15, "cascais": 30, "sintra": 28,
    "almada": 10, "seixal": 15, "barreiro": 20, "montijo": 20, "alcochete": 25,
    "loures": 15, "vila franca de xira": 32, "mafra": 40, "setubal": 48,
    "ericeira": 45, "azambuja": 50,
    "obidos": 85, "peniche": 95, "nazare": 123, "tomar": 145, "fatima": 123,
    "evora": 130, "alcacer do sal": 90, "santarem": 80, "caldas da rainha": 95,
    "leiria": 140, "coimbra": 200, "figueira da foz": 180,
    "porto": 314, "braga": 365, "guimaraes": 345, "aveiro": 250, "viseu": 290,
    "faro": 278, "lagos": 290, "albufeira": 255, "portimao": 285,
    "covilha": 300, "castelo branco": 255, "beja": 175, "elvas": 215,
}


def normalize_city(city):
    if not city:
        return ""
    text = unicodedata.normalize("NFKD", city).encode("ascii", "ignore").decode("ascii")
    return text.strip().lower()


def resolve_distance_km(city, explicit_distance_km):
    if explicit_distance_km is not None:
        try:
            return float(explicit_distance_km)
        except (TypeError, ValueError):
            pass
    return CITY_DISTANCE_KM.get(normalize_city(city))


def is_within_today_radius(city, distance_km):
    """Verdade se o evento for em Lisboa ou dentro do raio TODAY_RADIUS_KM."""
    norm = normalize_city(city)
    if norm in ("lisboa", "lisbon"):
        return True
    d = resolve_distance_km(city, distance_km)
    if d is None:
        return False  # sem informação de distância, não arriscamos para o dia de hoje
    return d <= TODAY_RADIUS_KM


PRICE_FREE_PATTERN = re.compile(
    r"\bgratis\b|\bgratuito\b|\bfree\b|entrada livre|sem custo|^\s*0\s*(e|eur|euros?)?\s*$",
)


def guess_is_free(price_text, is_free_flag):
    if is_free_flag is not None:
        return bool(is_free_flag)
    if not price_text:
        return None
    norm = normalize_city(str(price_text))
    return bool(PRICE_FREE_PATTERN.search(norm))


def parse_price_value(price_text):
    if not price_text:
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)", str(price_text))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def parse_event_hour(event_time):
    if not event_time:
        return None
    match = re.match(r"^(\d{1,2})", str(event_time).strip())
    if not match:
        return None
    hour = int(match.group(1))
    if 0 <= hour <= 23:
        return hour
    return None


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# Colunas novas que podem faltar numa BD criada antes desta versão.
EXTRA_EVENT_COLUMNS = {
    "event_date": "TEXT",       # data principal do evento (YYYY-MM-DD), usada para filtrar passado
    "event_date_end": "TEXT",   # fim do periodo, para exposicoes/eventos com duracao
    "event_time": "TEXT",       # hora HH:MM, opcional
    "distance_km": "REAL",      # distancia a Lisboa, se conhecida/fornecida
    "is_free": "INTEGER",       # 1 = gratuito, 0 = pago, NULL = desconhecido
    "image_url": "TEXT",        # foto ilustrativa do evento
    "snoozed_until": "TEXT",    # data (YYYY-MM-DD) em que um evento "adiado" volta a pending
}


def migrate_schema(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
    for col, col_type in EXTRA_EVENT_COLUMNS.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE events ADD COLUMN {col} {col_type}")
    conn.commit()


def init_db():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    conn = sqlite3.connect(DB_PATH)
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    migrate_schema(conn)
    # seed default rules if table is empty
    cur = conn.execute("SELECT COUNT(*) FROM rules")
    if cur.fetchone()[0] == 0:
        defaults_path = os.path.join(os.path.dirname(__file__), "rules_default.json")
        with open(defaults_path, "r", encoding="utf-8") as f:
            defaults = json.load(f)
        for r in defaults:
            conn.execute(
                "INSERT INTO rules (name, description, category, period_days, min_count, "
                "window_type, weekend_only, active) VALUES (?,?,?,?,?,?,?,1)",
                (r["name"], r["description"], r["category"], r["period_days"],
                 r["min_count"], r["window_type"], int(r.get("weekend_only", False))),
            )
        conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Scoring / learning
# ---------------------------------------------------------------------------

def get_weight(db, tag):
    row = db.execute("SELECT weight FROM preferences WHERE tag = ?", (tag,)).fetchone()
    return row["weight"] if row else 0.0


def adjust_weights(db, tags, delta):
    for tag in tags:
        tag = tag.strip().lower()
        if not tag:
            continue
        row = db.execute("SELECT weight FROM preferences WHERE tag = ?", (tag,)).fetchone()
        if row:
            db.execute("UPDATE preferences SET weight = weight + ? WHERE tag = ?", (delta, tag))
        else:
            db.execute("INSERT INTO preferences (tag, weight) VALUES (?, ?)", (tag, delta))
    db.commit()


def distance_score(distance_km):
    """Mais perto de Lisboa = melhor. 0km -> +5, 150km -> 0, mais longe -> 0 (sem penalizar viagens)."""
    if distance_km is None:
        return 0.0
    return max(0.0, 5.0 - (distance_km / 30.0))


def price_score(price_text, is_free_flag):
    free = guess_is_free(price_text, is_free_flag)
    if free is True:
        return 3.0
    value = parse_price_value(price_text)
    if value is None:
        return 0.0
    if value <= 10:
        return 1.0
    if value <= 25:
        return 0.0
    return -1.0


def time_score(event_time):
    """Horario pior à noite (Lara, 3 anos): manhã é melhor, noite/madrugada penalizado."""
    hour = parse_event_hour(event_time)
    if hour is None:
        return 0.0
    if 6 <= hour < 12:
        return 2.0
    if 12 <= hour < 18:
        return 1.0
    if 18 <= hour < 21:
        return -2.0
    return -4.0  # noite tardia / madrugada


def score_event(db, event_row):
    try:
        tags = json.loads(event_row["tags"]) if event_row["tags"] else []
    except (ValueError, TypeError):
        tags = []
    tag_score = sum(get_weight(db, t.strip().lower()) for t in tags)
    dist = resolve_distance_km(event_row["city"], event_row["distance_km"])
    return (
        tag_score
        + distance_score(dist)
        + price_score(event_row["price"], event_row["is_free"])
        + time_score(event_row["event_time"])
    )


def recompute_scores(db):
    rows = db.execute("SELECT * FROM events WHERE status = 'pending'").fetchall()
    for r in rows:
        s = score_event(db, r)
        db.execute("UPDATE events SET score = ? WHERE id = ?", (s, r["id"]))
    db.commit()


def reactivate_expired_snoozes(db):
    """Eventos 'adiados' cuja data de reaparecimento já passou voltam a 'pending'."""
    today_iso = date.today().isoformat()
    db.execute(
        "UPDATE events SET status='pending', snoozed_until=NULL "
        "WHERE status='snoozed' AND snoozed_until IS NOT NULL AND snoozed_until <= ?",
        (today_iso,),
    )
    db.commit()


def relevant_pending_query_rows(db):
    """Eventos pendentes, excluindo os que já passaram ou que hoje ficam fora do raio."""
    rows = db.execute(
        "SELECT * FROM events WHERE status = 'pending' ORDER BY score DESC, created_at DESC"
    ).fetchall()
    return filter_past_and_today_radius(rows)


def filter_past_and_today_radius(rows):
    """Aplica a regra: nunca mostrar eventos já passados; eventos de hoje só se perto/Lisboa."""
    today_iso = date.today().isoformat()
    filtered = []
    for r in rows:
        end = r["event_date_end"] or r["event_date"]
        if end and end < today_iso:
            continue
        if r["event_date"] == today_iso and not is_within_today_radius(r["city"], r["distance_km"]):
            continue
        filtered.append(r)
    return filtered


STATUS_LABELS = {
    "all": "Todos",
    "pending": "Proposto",
    "accepted": "Aceite",
    "rejected": "Rejeitado",
    "snoozed": "Adiado",
}


def build_filtered_events(db, status, category=None, date_from=None, date_to=None,
                           max_price=None, max_distance=None, free_only=False):
    """Lista eventos filtrados por estado + categoria/datas/preço/distância."""
    query = "SELECT * FROM events WHERE 1=1"
    params = []
    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
    if category:
        query += " AND category = ?"
        params.append(category)
    if date_from:
        query += " AND (event_date IS NULL OR event_date >= ?)"
        params.append(date_from)
    if date_to:
        query += " AND (event_date IS NULL OR event_date <= ?)"
        params.append(date_to)
    if status == "pending":
        query += " ORDER BY score DESC, created_at DESC"
    else:
        query += " ORDER BY COALESCE(chosen_date, event_date, created_at) DESC"
    rows = db.execute(query, params).fetchall()

    if status == "pending":
        rows = filter_past_and_today_radius(rows)
    elif status == "all":
        # dentro de "Todos", só aplicamos o filtro de passado/raio aos propostos;
        # aceites/rejeitados/adiados mostram-se sempre (são histórico/decisão já tomada).
        rows = [r for r in rows if r["status"] != "pending"] + \
               filter_past_and_today_radius([r for r in rows if r["status"] == "pending"])

    filtered = []
    for r in rows:
        if max_distance is not None:
            d = resolve_distance_km(r["city"], r["distance_km"])
            if d is None or d > max_distance:
                continue
        free = guess_is_free(r["price"], r["is_free"])
        if free_only and free is not True:
            continue
        if max_price is not None and free is not True:
            value = parse_price_value(r["price"])
            if value is not None and value > max_price:
                continue
        filtered.append(r)
    return filtered


# ---------------------------------------------------------------------------
# Rules engine
# ---------------------------------------------------------------------------

def check_rule(db, rule):
    """Retorna dict com status da regra (ok / at_risk / overdue) + detalhes."""
    today = date.today()
    period = timedelta(days=rule["period_days"])

    accepted = db.execute(
        "SELECT chosen_date FROM events WHERE category = ? AND status IN ('accepted','attended') "
        "AND chosen_date IS NOT NULL ORDER BY chosen_date DESC",
        (rule["category"],),
    ).fetchall()
    dates = [datetime.strptime(r["chosen_date"], "%Y-%m-%d").date() for r in accepted]

    # janela corrente: [hoje - period + 1dia, hoje] já cumprida? e próxima janela em risco?
    window_start = today - period + timedelta(days=1)
    count_in_window = sum(1 for d in dates if window_start <= d <= today)

    last_date = dates[0] if dates else None
    next_due = (last_date + period) if last_date else today

    status = "ok"
    if count_in_window < rule["min_count"]:
        if next_due < today:
            status = "overdue"
        elif (next_due - today).days <= 3:
            status = "at_risk"
        else:
            status = "ok"  # ainda dentro da janela de tolerância

    return {
        "rule": rule["name"],
        "description": rule["description"],
        "category": rule["category"],
        "status": status,
        "last_fulfilled": last_date.isoformat() if last_date else None,
        "next_due": next_due.isoformat(),
        "count_in_current_window": count_in_window,
        "min_count": rule["min_count"],
        "period_days": rule["period_days"],
    }


def all_rule_statuses(db):
    rules = db.execute("SELECT * FROM rules WHERE active = 1").fetchall()
    return [check_rule(db, dict(r)) for r in rules]


# ---------------------------------------------------------------------------
# Routes - UI
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    db = get_db()
    reactivate_expired_snoozes(db)
    recompute_scores(db)

    status = request.args.get("status", "pending")
    if status not in STATUS_LABELS:
        status = "pending"
    category = request.args.get("category") or None
    date_from = request.args.get("date_from") or None
    date_to = request.args.get("date_to") or None
    max_price = request.args.get("max_price", type=float)
    max_distance = request.args.get("max_distance", type=float)
    free_only = request.args.get("free_only") == "on"

    events = build_filtered_events(
        db, status, category=category, date_from=date_from, date_to=date_to,
        max_price=max_price, max_distance=max_distance, free_only=free_only,
    )
    rules_status = all_rule_statuses(db)
    return render_template(
        "dashboard.html",
        events=events,
        rules_status=rules_status,
        today=date.today().isoformat(),
        status=status,
        status_labels=STATUS_LABELS,
        filters={
            "category": category or "",
            "date_from": date_from or "",
            "date_to": date_to or "",
            "max_price": request.args.get("max_price", ""),
            "max_distance": request.args.get("max_distance", ""),
            "free_only": free_only,
        },
    )


@app.route("/events/<int:event_id>/accept", methods=["POST"])
def accept_event(event_id):
    db = get_db()
    chosen_date = request.form.get("chosen_date") or date.today().isoformat()
    ev = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if ev:
        db.execute(
            "UPDATE events SET status='accepted', chosen_date=?, decided_at=? WHERE id=?",
            (chosen_date, datetime.utcnow().isoformat(), event_id),
        )
        db.commit()
        adjust_weights(db, json.loads(ev["tags"] or "[]"), +1.0)
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/events/<int:event_id>/reject", methods=["POST"])
def reject_event(event_id):
    db = get_db()
    ev = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if ev:
        db.execute(
            "UPDATE events SET status='rejected', decided_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), event_id),
        )
        db.commit()
        adjust_weights(db, json.loads(ev["tags"] or "[]"), -1.0)
    return redirect(request.referrer or url_for("dashboard"))


SNOOZE_DEFAULT_DAYS = 14


@app.route("/events/<int:event_id>/snooze", methods=["POST"])
def snooze_event(event_id):
    """Adia um evento: fica fora da lista de pendentes até snoozed_until, sem afetar pesos."""
    db = get_db()
    ev = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if ev:
        try:
            days = int(request.form.get("snooze_days") or SNOOZE_DEFAULT_DAYS)
        except ValueError:
            days = SNOOZE_DEFAULT_DAYS
        snoozed_until = (date.today() + timedelta(days=days)).isoformat()
        db.execute(
            "UPDATE events SET status='snoozed', snoozed_until=? WHERE id=?",
            (snoozed_until, event_id),
        )
        db.commit()
    return redirect(request.referrer or url_for("dashboard"))


MONTH_NAMES_PT = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
WEEKDAY_NAMES_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def add_months(d, n):
    month_index = d.month - 1 + n
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def event_fallback_image(category):
    safe_category = category if category in ("concert", "cultural", "trip") else "other"
    return url_for("static", filename=f"img/{safe_category}.svg")


def build_month_grid(month_start, events_by_date):
    import calendar as calmod
    cal = calmod.Calendar(firstweekday=0)  # semana começa à segunda
    weeks = cal.monthdayscalendar(month_start.year, month_start.month)
    grid_weeks = []
    for week in weeks:
        week_cells = []
        for day in week:
            if day == 0:
                week_cells.append(None)
                continue
            iso = date(month_start.year, month_start.month, day).isoformat()
            evs = events_by_date.get(iso, [])
            week_cells.append({
                "day": day,
                "date": iso,
                "has_accepted": any(e["status"] == "accepted" for e in evs),
                "has_pending": any(e["status"] == "pending" for e in evs),
                "events": evs,
            })
        grid_weeks.append(week_cells)
    return {
        "label": f"{MONTH_NAMES_PT[month_start.month]} {month_start.year}",
        "weeks": grid_weeks,
    }


@app.route("/calendario")
def calendar_view():
    db = get_db()
    reactivate_expired_snoozes(db)

    month_starts = [add_months(date.today().replace(day=1), i) for i in range(3)]
    range_start = month_starts[0].isoformat()
    last_month = month_starts[-1]
    import calendar as calmod
    last_day = calmod.monthrange(last_month.year, last_month.month)[1]
    range_end = date(last_month.year, last_month.month, last_day).isoformat()

    rows = db.execute(
        "SELECT * FROM events WHERE "
        "(status = 'accepted' AND chosen_date BETWEEN ? AND ?) "
        "OR (status = 'pending' AND event_date BETWEEN ? AND ?)",
        (range_start, range_end, range_start, range_end),
    ).fetchall()

    pending_rows = filter_past_and_today_radius([r for r in rows if r["status"] == "pending"])
    pending_ids = {r["id"] for r in pending_rows}
    relevant_rows = [r for r in rows if r["status"] == "accepted" or r["id"] in pending_ids]

    events_by_date = {}
    for r in relevant_rows:
        day_key = r["chosen_date"] if r["status"] == "accepted" else r["event_date"]
        if not day_key:
            continue
        events_by_date.setdefault(day_key, []).append({
            "id": r["id"],
            "title": r["title"],
            "category": r["category"],
            "status": r["status"],
            "status_label": STATUS_LABELS.get(r["status"], r["status"]),
            "city": r["city"],
            "venue": r["venue"],
            "event_time": r["event_time"],
            "price": r["price"],
            "is_free": bool(r["is_free"]) if r["is_free"] is not None else None,
            "distance_km": r["distance_km"],
            "image_url": r["image_url"] or event_fallback_image(r["category"]),
            "source_url": r["source_url"],
        })

    month_grids = [build_month_grid(m, events_by_date) for m in month_starts]

    return render_template(
        "calendar.html",
        month_grids=month_grids,
        events_by_date_json=json.dumps(events_by_date, ensure_ascii=False).replace("</", "<\\/"),
        today=date.today().isoformat(),
        weekday_names=WEEKDAY_NAMES_PT,
    )


@app.route("/events/manual", methods=["POST"])
def add_manual_event():
    db = get_db()
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    is_free_raw = request.form.get("is_free")
    is_free = 1 if is_free_raw == "on" else None
    db.execute(
        "INSERT INTO events (title, category, city, country, venue, event_date, event_date_end, "
        "event_time, distance_km, is_free, image_url, tags, source_url, price, notes, status, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'pending', ?)",
        (
            request.form.get("title"),
            request.form.get("category"),
            request.form.get("city"),
            request.form.get("country"),
            request.form.get("venue"),
            request.form.get("event_date") or None,
            request.form.get("event_date_end") or None,
            request.form.get("event_time") or None,
            request.form.get("distance_km") or None,
            is_free,
            request.form.get("image_url") or None,
            json.dumps(tags),
            request.form.get("source_url"),
            request.form.get("price"),
            request.form.get("notes"),
            datetime.utcnow().isoformat(),
        ),
    )
    db.commit()
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Routes - API (usadas pelo cron do Hermes: alimentar eventos + consultar status)
# ---------------------------------------------------------------------------

def require_api_key():
    key = request.headers.get("X-API-Key")
    if key != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    return None


@app.route("/api/events/<int:event_id>", methods=["PATCH"])
def api_update_event(event_id):
    """Atualiza campos pontuais de um evento existente (ex. corrigir event_date_end
    quando a fonte original não indicava a duração real do evento)."""
    unauthorized = require_api_key()
    if unauthorized:
        return unauthorized
    db = get_db()
    ev = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not ev:
        return jsonify({"error": "not_found"}), 404
    payload = request.get_json(force=True) or {}
    allowed = {"event_date", "event_date_end", "event_time", "notes", "distance_km", "source_url"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        return jsonify({"error": "no_valid_fields", "allowed": sorted(allowed)}), 400
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    db.execute(f"UPDATE events SET {set_clause} WHERE id = ?", (*updates.values(), event_id))
    db.commit()
    updated = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return jsonify({k: updated[k] for k in ("id", "title", "event_date", "event_date_end", "event_time")})


def should_skip_event(item):
    """Decide se um evento candidato deve ser ignorado: já passou, ou é hoje mas longe."""
    today_iso = date.today().isoformat()
    event_date = item.get("event_date")
    event_date_end = item.get("event_date_end")

    if not event_date and item.get("date_options"):
        opts = item.get("date_options") or []
        if opts:
            event_date = sorted(opts)[0]

    if event_date:
        relevant_end = event_date_end or event_date
        if relevant_end < today_iso:
            return True, "evento já passou"
        if event_date == today_iso:
            if not is_within_today_radius(item.get("city"), item.get("distance_km")):
                return True, "evento é hoje e está fora do raio de 50km / não é em Lisboa"
    return False, None


@app.route("/api/events", methods=["POST"])
def api_add_events():
    unauthorized = require_api_key()
    if unauthorized:
        return unauthorized
    db = get_db()
    payload = request.get_json(force=True)
    items = payload if isinstance(payload, list) else [payload]
    inserted = 0
    skipped = []
    for item in items:
        skip, reason = should_skip_event(item)
        if skip:
            skipped.append({"title": item.get("title"), "reason": reason})
            continue
        # evita duplicados óbvios pelo título+cidade
        existing = db.execute(
            "SELECT id FROM events WHERE title = ? AND city = ?", (item.get("title"), item.get("city"))
        ).fetchone()
        if existing:
            continue

        event_date = item.get("event_date")
        if not event_date and item.get("date_options"):
            opts = item.get("date_options") or []
            if opts:
                event_date = sorted(opts)[0]

        is_free_flag = item.get("is_free")
        db.execute(
            "INSERT INTO events (title, category, city, country, venue, date_options, event_date, "
            "event_date_end, event_time, distance_km, is_free, image_url, tags, source_url, price, "
            "notes, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'pending', ?)",
            (
                item.get("title"),
                item.get("category"),
                item.get("city"),
                item.get("country"),
                item.get("venue"),
                json.dumps(item.get("date_options", [])),
                event_date,
                item.get("event_date_end"),
                item.get("event_time"),
                item.get("distance_km"),
                (1 if is_free_flag else (0 if is_free_flag is False else None)),
                item.get("image_url"),
                json.dumps(item.get("tags", [])),
                item.get("source_url"),
                item.get("price"),
                item.get("notes"),
                datetime.utcnow().isoformat(),
            ),
        )
        inserted += 1
    db.commit()
    return jsonify({"inserted": inserted, "received": len(items), "skipped": skipped})


@app.route("/api/preferences", methods=["POST"])
def api_set_preferences():
    """Permite seedar/ajustar pesos de preferencia manualmente. Body: [{"tag":"rock","weight":2}, ...]"""
    unauthorized = require_api_key()
    if unauthorized:
        return unauthorized
    db = get_db()
    payload = request.get_json(force=True)
    items = payload if isinstance(payload, list) else [payload]
    for item in items:
        tag = (item.get("tag") or "").strip().lower()
        weight = float(item.get("weight", 0))
        if not tag:
            continue
        row = db.execute("SELECT id FROM preferences WHERE tag = ?", (tag,)).fetchone()
        if row:
            db.execute("UPDATE preferences SET weight = ? WHERE tag = ?", (weight, tag))
        else:
            db.execute("INSERT INTO preferences (tag, weight) VALUES (?, ?)", (tag, weight))
    db.commit()
    return jsonify({"updated": len(items)})


@app.route("/api/rules/status")
def api_rules_status():
    unauthorized = require_api_key()
    if unauthorized:
        return unauthorized
    db = get_db()
    return jsonify(all_rule_statuses(db))


@app.route("/api/recommendations/top")
def api_top_recommendations():
    unauthorized = require_api_key()
    if unauthorized:
        return unauthorized
    db = get_db()
    reactivate_expired_snoozes(db)
    recompute_scores(db)
    limit = int(request.args.get("limit", 3))
    rows = relevant_pending_query_rows(db)[:limit]
    cols = ["title", "category", "city", "score", "tags", "source_url", "event_date",
            "event_time", "distance_km", "is_free", "price", "image_url"]
    return jsonify([{c: r[c] for c in cols} for r in rows])


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
else:
    # quando corrido via gunicorn/WSGI em produção
    init_db()
