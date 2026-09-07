import time
import feedparser
from app import app, db, Podcast, Episode, slugify

# Frecuencia de chequeo en segundos (3600 = 1 hora)
INTERVALO = 3600 

def sincronizar_podcasts():
    # Entramos al modo Flask para poder usar la Base de Datos
    with app.app_context():
        podcasts = Podcast.query.filter_by(es_dinamico=True).all()
        
        if not podcasts:
            print("💤 No hay podcasts espejo configurados. Volviendo a dormir...", flush=True)
            return

        for podcast in podcasts:
            print(f"🔄 Revisando espejo: {podcast.title}", flush=True)
            try:
                feed = feedparser.parse(podcast.rss_url)
                
                # Leemos los episodios del RSS (los primeros 20 para no saturar)
                for entry in feed.entries[:20]:
                    ep_title = entry.title
                    ep_slug = slugify(ep_title)
                    
                    # ¿Ya tenemos este episodio guardado?
                    existe = Episode.query.filter_by(podcast_id=podcast.id, slug=ep_slug).first()
                    
                    if not existe:
                        # Buscamos el link directo al audio original
                        audio_url = entry.enclosures[0].href if entry.enclosures else None
                        
                        if audio_url:
                            print(f"✨ Nuevo episodio descargado: {ep_title}", flush=True)
                            
                            description = entry.get('summary', entry.get('description', 'Sin descripción'))
                            
                            # Extraer duración si el RSS la provee (sino queda 00:00:00)
                            duration = "00:00:00"
                            if 'itunes_duration' in entry:
                                duration = entry.itunes_duration
                            
                            nuevo_ep = Episode(
                                podcast_id=podcast.id,
                                title=ep_title,
                                slug=ep_slug,
                                description=description,
                                audio_file=audio_url, # ¡Guardamos la URL directa, no el archivo local!
                                duration=duration,
                                byte_size=0 # No ocupa espacio en tu servidor
                            )
                            db.session.add(nuevo_ep)
                
                # Guardamos los cambios en la BD
                db.session.commit()
                print(f"✅ Espejo '{podcast.title}' sincronizado.", flush=True)
                
            except Exception as e:
                print(f"❌ Error sincronizando {podcast.title}: {e}", flush=True)

if __name__ == '__main__':
    print("🚀 Iniciando Motor Sincronizador de RSS (Espejos)...", flush=True)
    while True:
        sincronizar_podcasts()
        print(f"⏳ Esperando {INTERVALO/60} minutos para el próximo chequeo...", flush=True)
        time.sleep(INTERVALO)
