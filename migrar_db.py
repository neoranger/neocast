#!/usr/bin/env python3
"""
Migración idempotente de la base de datos de NeoCast.

db.create_all() (que corre al arrancar app.py) NO altera tablas existentes,
así que las columnas de la sincronización de podcasts remotos se deben agregar
con este script una sola vez:

    python migrar_db.py            # aplica los cambios
    python migrar_db.py --dry-run  # solo muestra qué haría

Después de aplicarla, reiniciá la app (o el contenedor) para levantar el hilo
de sincronización con las columnas nuevas.
"""
import os
import sys
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'neocast.db')

COLUMNS = {
    'es_dinamico': 'BOOLEAN NOT NULL DEFAULT 0',
    'rss_url': 'VARCHAR(500)',
    'es_mirror': 'BOOLEAN NOT NULL DEFAULT 0',
    'last_synced_at': 'DATETIME',
}


def main():
    dry_run = '--dry-run' in sys.argv

    if not os.path.exists(DB_PATH):
        print(f"❌ No se encuentra la base de datos: {DB_PATH}")
        print("   Levantá la app al menos una vez (crea data/neocast.db) antes de migrar.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    table = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='podcast'"
    ).fetchone()
    if not table:
        print("❌ La tabla 'podcast' no existe en la base de datos.")
        conn.close()
        sys.exit(1)

    existing = {row[1] for row in cur.execute('PRAGMA table_info(podcast)')}
    to_add = {col: ddl for col, ddl in COLUMNS.items() if col not in existing}

    if not to_add:
        print("✅ La base de datos ya tiene todas las columnas. Nada que hacer.")
    else:
        for col, ddl in to_add.items():
            sql = f"ALTER TABLE podcast ADD COLUMN {col} {ddl}"
            print(("🔍 (dry-run) " if dry_run else "➕ ") + sql)
            if not dry_run:
                cur.execute(sql)

    if not dry_run:
        conn.commit()
    conn.close()

    if to_add and not dry_run:
        print("\n✅ Migración aplicada. Reiniciá la app (o el contenedor) para levantar el hilo de sync.")

if __name__ == '__main__':
    main()