#!/bin/bash

# 1. Definimos la carpeta donde se guardarán los backups
BACKUP_DIR="./backups"
mkdir -p "$BACKUP_DIR"

# 2. Creamos una marca de tiempo (Ej: 2026-02-23_19-30-00)
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="$BACKUP_DIR/neocast_backup_$TIMESTAMP.tar.gz"

echo "📦 Iniciando backup de NeoCast..."

# 3. Comprimimos las carpetas críticas (Base de datos y Audios)
# Usamos -c (crear), -z (comprimir con gzip), -f (archivo)
tar -czf "$BACKUP_FILE" data static

echo "✅ Backup completado con éxito: $BACKUP_FILE"

# 4. LIMPIEZA AUTOMÁTICA: Borrar backups que tengan más de 7 días
find "$BACKUP_DIR" -type f -name "*.tar.gz" -mtime +7 -exec rm {} \;
echo "🧹 Limpieza de backups antiguos (más de 7 días) completada."
