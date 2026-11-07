"""
Script de limpeza pontual: remove eventos duplicados já existentes na BD,
usando a MESMA lógica de deteção de duplicados do app.py (score combinado de
título + local + data — ver find_duplicate_event em app.py, item 17 do
backlog). Mantém sempre consistência: se um grupo é duplicado aqui, também
seria detetado como tal na importação via /api/events.

Mantém o registo "melhor" de cada grupo de duplicados por esta ordem de
prioridade:
  1. status != 'pending' (um evento já aceite/rejeitado/adiado tem
     informação do utilizador que não queremos perder)
  2. tiver image_url preenchido
  3. id mais baixo (mais antigo)

Uso (local ou na consola Bash do PythonAnywhere, dentro do venv da app):
    python dedupe_events.py            # mostra o que seria removido (dry-run)
    python dedupe_events.py --apply    # remove de facto

Usa o mesmo EVENTOS_DB_PATH que a app usa (ou 'eventos.db' local por
omissão), para apontar sempre à BD correta.
"""
import difflib
import os
import re
import sqlite3
import sys
import unicodedata
from datetime import date

TITLE_GATE = 0.65
DUP_THRESHOLD = 0.75
W_TITLE, W_LOC, W_DATE = 0.6, 0.2, 0.2


def normalize_event_title(title):
    if not title:
        return ""
    t = unicodedata.normalize("NFKD", title)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def title_similarity(a, b):
    norm_a = normalize_event_title(a)
    norm_b = normalize_event_title(b)
    direct = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()
    sorted_a = " ".join(sorted(norm_a.split()))
    sorted_b = " ".join(sorted(norm_b.split()))
    token_sorted = difflib.SequenceMatcher(None, sorted_a, sorted_b).ratio()
    return max(direct, token_sorted)


def date_similarity(date_a, date_b):
    if not date_a or not date_b:
        return 0.5
    try:
        d1 = date.fromisoformat(date_a)
        d2 = date.fromisoformat(date_b)
    except ValueError:
        return 1.0 if date_a == date_b else 0.0
    diff_days = abs((d1 - d2).days)
    if diff_days == 0:
        return 1.0
    if diff_days >= 7:
        return 0.0
    return max(0.0, 1.0 - diff_days / 7)


def location_similarity(a, b):
    loc_a = f"{a.get('venue') or ''} {a.get('city') or ''}"
    loc_b = f"{b.get('venue') or ''} {b.get('city') or ''}"
    norm_a = normalize_event_title(loc_a)
    norm_b = normalize_event_title(loc_b)
    if not norm_a and not norm_b:
        return 0.5
    if not norm_a or not norm_b:
        return 0.3
    return difflib.SequenceMatcher(None, norm_a, norm_b).ratio()


def is_duplicate(a, b):
    title_sim = title_similarity(a["title"], b["title"])
    if title_sim < TITLE_GATE:
        return False
    date_sim = date_similarity(a["event_date"], b["event_date"])
    loc_sim = location_similarity(a, b)
    score = W_TITLE * title_sim + W_LOC * loc_sim + W_DATE * date_sim
    return score >= DUP_THRESHOLD


def rank_key(row):
    # menor = melhor (mantido)
    return (
        0 if row["status"] != "pending" else 1,
        0 if row["image_url"] else 1,
        row["id"],
    )


def find_duplicate_groups(rows):
    seen = set()
    groups = []
    for i, row in enumerate(rows):
        if row["id"] in seen:
            continue
        group = [row]
        for other in rows[i + 1 :]:
            if other["id"] in seen:
                continue
            if any(is_duplicate(other, g) for g in group):
                group.append(other)
        if len(group) > 1:
            groups.append(group)
            seen.update(g["id"] for g in group)
    return groups


def main():
    apply_changes = "--apply" in sys.argv
    db_path = os.environ.get("EVENTOS_DB_PATH", "eventos.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, title, city, venue, event_date, status, image_url FROM events ORDER BY id"
    ).fetchall()
    rows = [dict(r) for r in rows]

    groups = find_duplicate_groups(rows)
    if not groups:
        print("Nenhum duplicado encontrado.")
        return

    to_delete = []
    for group in groups:
        group_sorted = sorted(group, key=rank_key)
        keep = group_sorted[0]
        remove = group_sorted[1:]
        print(f"\nGrupo (mantém #{keep['id']} '{keep['title']}' [{keep['venue']}, {keep['event_date']}] [{keep['status']}]):")
        for r in remove:
            print(f"  remove #{r['id']} '{r['title']}' [{r['venue']}, {r['event_date']}] [{r['status']}]")
            to_delete.append(r["id"])

    print(f"\nTotal de grupos duplicados: {len(groups)} | eventos a remover: {len(to_delete)}")

    if apply_changes:
        conn.executemany("DELETE FROM events WHERE id = ?", [(i,) for i in to_delete])
        conn.commit()
        print("Removidos.")
    else:
        print("Dry-run (nada foi removido). Corre com --apply para aplicar.")

    conn.close()


if __name__ == "__main__":
    main()
