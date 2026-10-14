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
"""
import json
import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, g, jsonify, redirect, render_template, request, url_for

DB_PATH = os.environ.get("EVENTOS_DB_PATH", os.path.join(os.path.dirname(__file__), "eventos.db"))
API_KEY = os.environ.get("EVENTOS_API_KEY", "changeme-dev-key")

app = Flask(__name__)


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


def init_db():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    conn = sqlite3.connect(DB_PATH)
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
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


def score_event(db, tags_json):
    try:
        tags = json.loads(tags_json) if tags_json else []
    except (ValueError, TypeError):
        tags = []
    return sum(get_weight(db, t.strip().lower()) for t in tags)


def recompute_scores(db):
    rows = db.execute("SELECT id, tags FROM events WHERE status = 'pending'").fetchall()
    for r in rows:
        s = score_event(db, r["tags"])
        db.execute("UPDATE events SET score = ? WHERE id = ?", (s, r["id"]))
    db.commit()


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
    recompute_scores(db)
    pending = db.execute(
        "SELECT * FROM events WHERE status = 'pending' ORDER BY score DESC, created_at DESC"
    ).fetchall()
    upcoming = db.execute(
        "SELECT * FROM events WHERE status = 'accepted' AND chosen_date >= ? ORDER BY chosen_date ASC",
        (date.today().isoformat(),),
    ).fetchall()
    rules_status = all_rule_statuses(db)
    return render_template(
        "dashboard.html",
        pending=pending,
        upcoming=upcoming,
        rules_status=rules_status,
        today=date.today().isoformat(),
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
    return redirect(url_for("dashboard"))


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
    return redirect(url_for("dashboard"))


@app.route("/events/manual", methods=["POST"])
def add_manual_event():
    db = get_db()
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    db.execute(
        "INSERT INTO events (title, category, city, country, venue, tags, source_url, price, "
        "notes, status, created_at) VALUES (?,?,?,?,?,?,?,?,?, 'pending', ?)",
        (
            request.form.get("title"),
            request.form.get("category"),
            request.form.get("city"),
            request.form.get("country"),
            request.form.get("venue"),
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


@app.route("/api/events", methods=["POST"])
def api_add_events():
    unauthorized = require_api_key()
    if unauthorized:
        return unauthorized
    db = get_db()
    payload = request.get_json(force=True)
    items = payload if isinstance(payload, list) else [payload]
    inserted = 0
    for item in items:
        # evita duplicados óbvios pelo título+data+cidade
        existing = db.execute(
            "SELECT id FROM events WHERE title = ? AND city = ?", (item.get("title"), item.get("city"))
        ).fetchone()
        if existing:
            continue
        db.execute(
            "INSERT INTO events (title, category, city, country, venue, date_options, tags, "
            "source_url, price, notes, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?, 'pending', ?)",
            (
                item.get("title"),
                item.get("category"),
                item.get("city"),
                item.get("country"),
                item.get("venue"),
                json.dumps(item.get("date_options", [])),
                json.dumps(item.get("tags", [])),
                item.get("source_url"),
                item.get("price"),
                item.get("notes"),
                datetime.utcnow().isoformat(),
            ),
        )
        inserted += 1
    db.commit()
    return jsonify({"inserted": inserted, "received": len(items)})


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
    recompute_scores(db)
    limit = int(request.args.get("limit", 3))
    rows = db.execute(
        "SELECT title, category, city, score, tags, source_url FROM events "
        "WHERE status='pending' ORDER BY score DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        init_db()
    else:
        # garante que tabelas novas/regras default existem mesmo com DB já criado
        init_db()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
else:
    # quando corrido via gunicorn/WSGI em produção
    init_db()
