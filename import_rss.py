import sys
import os
import time
import uuid
import requests
import feedparser
from datetime import datetime
from time import mktime
from werkzeug.utils import secure_filename

# Importamos las herramientas
from app import app, db, Podcast, Episode, slugify, MEDIA_DIR

def download_file(url, prefix=""):
    """Descarga un archivo y lo guarda con un nombre 100% único."""
    if not url: return None
    
    try:
        print(f"    ⬇️ Descargando: {url.split('/')[-1][:30]}...")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        ext = url.split('.')[-1][:4]
        if '?' in ext: ext = ext.split('?')[0]
        if not ext.isalnum(): ext = 'mp3'
        
        # Usamos UUID en lugar del tiempo para que jamás se repitan
        unique_id = uuid.uuid4().hex[:8] 
        filename = secure_filename(f"{prefix}_{unique_id}.{ext}")
        filepath = os.path.join(MEDIA_DIR, filename)
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return filename
    except Exception as e:
        print(f"    ❌ Error descargando {url}: {e}")
        return None

def import_podcast(feed_url):
    print(f"\n📡 Analizando feed RSS: {feed_url}")
    feed = feedparser.parse(feed_url)
    
    if feed.bozo:
        print("❌ Error: No se pudo leer el RSS. Verifica la URL.")
        return

    title = feed.feed.get('title', 'Podcast Importado')
    author = feed.feed.get('author', feed.feed.get('itunes_author', 'Desconocido'))
    description = feed.feed.get('summary', feed.feed.get('description', 'Sin descripción'))
    
    category = ""
    if 'tags' in feed.feed:
        category = feed.feed.tags[0].term

    print(f"\n🎙️  Creando programa: {title}")
    
    cover_url = None
    if 'image' in feed.feed:
        cover_url = feed.feed.image.href
    elif 'itunes_image' in feed.feed:
        cover_url = feed.feed.itunes_image.get('href')
        
    cover_filename = download_file(cover_url, "cover")

    with app.app_context():
        new_pod = Podcast(
            title=title,
            slug=f"{slugify(title)}-{uuid.uuid4().hex[:6]}",
            description=description,
            author=author,
            category=category,
            cover_image=cover_filename
        )
        db.session.add(new_pod)
        db.session.commit()
        podcast_id = new_pod.id

        print(f"✅ Programa creado con ID: {podcast_id}")
        print(f"📦 Encontrados {len(feed.entries)} episodios. Iniciando descarga...\n")

        for entry in reversed(feed.entries):
            ep_title = entry.get('title', 'Episodio sin título')
            print(f"▶️  Procesando: {ep_title}")
            
            ep_desc = entry.get('content', [{'value': entry.get('summary', '')}])[0]['value']
            
            pub_date = datetime.utcnow()
            if 'published_parsed' in entry:
                pub_date = datetime.fromtimestamp(mktime(entry.published_parsed))
                
            # Traductor inteligente de duraciones (Segundos vs HH:MM:SS)
            raw_duration = entry.get('itunes_duration', '00:00:00')
            if isinstance(raw_duration, str) and raw_duration.isdigit():
                total_seconds = int(raw_duration)
                hours = total_seconds // 3600
                mins = (total_seconds % 3600) // 60
                secs = total_seconds % 60
                duration = f"{hours:02d}:{mins:02d}:{secs:02d}"
            elif isinstance(raw_duration, str) and ':' in raw_duration:
                parts = raw_duration.split(':')
                if len(parts) == 2:
                    duration = f"00:{int(parts[0]):02d}:{int(parts[1]):02d}"
                else:
                    duration = raw_duration
            else:
                duration = "00:00:00"
            
            audio_url = None
            byte_size = 0
            for link in entry.get('links', []):
                if link.get('rel') == 'enclosure':
                    audio_url = link.get('href')
                    byte_size = link.get('length', 0)
                    break
            
            if audio_url:
                audio_filename = download_file(audio_url, "ep")
                
                if not byte_size and audio_filename:
                    filepath = os.path.join(MEDIA_DIR, audio_filename)
                    if os.path.exists(filepath):
                        byte_size = os.path.getsize(filepath)
                
                if audio_filename:
                    # Bloque de seguridad para la base de datos
                    try:
                        new_ep = Episode(
                            podcast_id=podcast_id,
                            title=ep_title,
                            slug=f"{slugify(ep_title)}-{uuid.uuid4().hex[:6]}", # Identificador único para la URL
                            description=ep_desc,
                            audio_file=audio_filename,
                            duration=str(duration),
                            byte_size=int(byte_size),
                            pub_date=pub_date,
                            listens=0
                        )
                        db.session.add(new_ep)
                        db.session.commit()
                        print(f"    ✅ Guardado en base de datos.")
                    except Exception as e:
                        db.session.rollback() # Cancelamos la operación fallida para que no se tranque la base de datos
                        print(f"    ❌ Error en base de datos con este episodio: {e}")
            else:
                print(f"    ⚠️ No se encontró audio. Saltando.")

        print("\n🎉 ¡Importación completada con éxito!")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python import_rss.py <URL_DEL_RSS>")
        sys.exit(1)
    
    rss_url = sys.argv[1]
    import_podcast(rss_url)
