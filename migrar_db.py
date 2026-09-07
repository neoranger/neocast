import sqlite3
import os

# Apuntamos al archivo de tu base de datos
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', 'neocast.db')

print(f"Conectando a {db_path}...")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Agregamos la columna booleana (0 es False en SQLite)
    cursor.execute("ALTER TABLE podcast ADD COLUMN es_dinamico BOOLEAN DEFAULT 0;")
    print("✅ Columna 'es_dinamico' agregada.")
    
    # Agregamos la columna de texto
    cursor.execute("ALTER TABLE podcast ADD COLUMN rss_url VARCHAR(255);")
    print("✅ Columna 'rss_url' agregada.")
    
    conn.commit()
    print("🎉 ¡Migración exitosa! Tu base de datos está intacta y actualizada.")
except Exception as e:
    print(f"⚠️ Error (quizás las columnas ya existían): {e}")

finally:
    conn.close()
