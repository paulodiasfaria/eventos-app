"""
Script de limpeza pontual: remove eventos duplicados já existentes na BD
(título igual ou muito semelhante >=85% + mesma data, com tolerância de 2
dias, ou mesma cidade quando nenhum dos dois tem data).

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
import os
import re
import sqlite3
import sys
import unicodedata
from datetime import date


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
    import difflib

    return difflib.SequenceMatcher(None, normalize_event_title(a), normalize_event_title(b)).ratio()


def dates_close(d1, d2, max_days=2):
    if not d1 or not d2:
        return False
    try:
        return abs((date.fromisoformat(d1) - date.fromisoformat(d2)).days) <= max_days
    except ValueError:
        return d1 == d2


def is_duplicate(a, b):
    if title_similarity(a["title"], b["title"]) < 0.85:
        return False
    if a["event_date"] and b["event_date"]:
        return dates_close(a["event_date"], b["event_date"])
    if not a["event_date"] and not b["event_date"]:
        return (a["city"] or "").strip().lower() == (b["city"] or "").strip().lower()
    return False


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
        "SELECT id, title, city, event_date, status, image_url FROM events ORDER BY id"
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
        print(f"\nGrupo (mantém #{keep['id']} '{keep['title']}' [{keep['event_date']}] [{keep['status']}]):")
        for r in remove:
            print(f"  remove #{r['id']} '{r['title']}' [{r['event_date']}] [{r['status']}]")
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
