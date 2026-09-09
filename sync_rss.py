#!/usr/bin/env python3
"""
Sincronización de podcasts importados desde RSS externo.

Re-fetchea el feed original de cada podcast remoto y agrega los episodios
nuevos (sin duplicados), respetando el modo del import original:
  - Modo espejo (es_mirror=True):  guarda la URL de audio del feed original.
  - Modo local (es_mirror=False):  descarga el MP3 al servidor.

Se ejecuta automáticamente en segundo plano mediante el hilo de la app, pero
también se puede correr a mano (p. ej. para una sincronización forzada):

    python sync_rss.py --all
    python sync_rss.py --podcast 3
"""
import sys
import os
import uuid
import argparse
import requests
import feedparser
from datetime import datetime
from time import mktime

from app import app, db, Podcast, Episode, slugify, MEDIA_DIR
from import_rss import HEADERS, download_file, parse_duration


def fetch_feed(rss_url):
    response = requests.get(rss_url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return feedparser.parse(response.content)


def sync_podcast(podcast):
    """Actualiza un podcast remoto con los episodios nuevos. Devuelve la cantidad agregada."""
    if not podcast.rss_url:
        return 0

    feed = fetch_feed(podcast.rss_url)
    if not feed.entries and not feed.feed:
        raise ValueError("Feed vacío o no legible.")

    existing_titles = {e.title.strip().lower() for e in podcast.episodes}
    added = 0

    for entry in reversed(feed.entries):
        ep_title = entry.get('title', 'Episodio sin título')
        if ep_title.strip().lower() in existing_titles:
            continue

        ep_desc = entry.get('content', [{'value': entry.get('summary', '')}])[0]['value']

        pub_date = datetime.utcnow()
        parsed = entry.get('published_parsed') or entry.get('updated_parsed')
        if parsed:
            pub_date = datetime.fromtimestamp(mktime(parsed))

        duration = parse_duration(entry.get('itunes_duration', '00:00:00'))

        audio_url = None
        byte_size = 0
        for link in entry.get('links', []):
            if link.get('rel') == 'enclosure':
                audio_url = link.get('href')
                byte_size = int(link.get('length') or 0)
                break

        if not audio_url:
            print(f"    ⚠️ '{ep_title}': sin audio, se omite.", flush=True)
            continue

        if podcast.es_mirror:
            audio_filename = audio_url
        else:
            audio_filename = download_file(audio_url, "ep")
            if not audio_filename:
                continue
            filepath = os.path.join(MEDIA_DIR, audio_filename)
            if os.path.exists(filepath):
                byte_size = os.path.getsize(filepath)

        try:
            new_ep = Episode(
                podcast_id=podcast.id,
                title=ep_title,
                slug=f"{slugify(ep_title)}-{uuid.uuid4().hex[:6]}",
                description=ep_desc,
                audio_file=audio_filename,
                duration=duration,
                byte_size=byte_size,
                pub_date=pub_date,
                listens=0
            )
            db.session.add(new_ep)
            db.session.commit()
            print(f"    ✅ Nuevo episodio: {ep_title}", flush=True)
            added += 1
        except Exception as e:
            db.session.rollback()
            print(f"    ❌ Error guardando '{ep_title}': {e}", flush=True)

    podcast.last_synced_at = datetime.utcnow()
    db.session.commit()
    return added


def sync_all():
    """Sincroniza todos los podcasts remotos. Devuelve un resumen en texto."""
    with app.app_context():
        podcasts = (Podcast.query
                    .filter(Podcast.es_dinamico == True)
                    .filter(Podcast.rss_url.isnot(None))
                    .all())

        if not podcasts:
            return "Sin podcasts remotos (es_dinamico + rss_url) para sincronizar."

        lines = [f"{len(podcasts)} podcast(s) remoto(s):"]
        for p in podcasts:
            try:
                added = sync_podcast(p)
                lines.append(f"  ✅ {p.title}: {added} episodio(s) nuevos")
            except Exception as e:
                db.session.rollback()
                lines.append(f"  ❌ {p.title}: {e}")

        return "\n".join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Sincroniza podcasts importados desde RSS externo.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--all', action='store_true', help='Sincronizar todos los podcasts remotos')
    group.add_argument('--podcast', type=int, metavar='ID', help='Sincronizar un solo podcast por ID')
    args = parser.parse_args()

    if not args.all and args.podcast is None:
        parser.print_help()
        sys.exit(1)

    if args.podcast is not None:
        with app.app_context():
            p = db.session.get(Podcast, args.podcast)
            if p is None:
                print(f"❌ No existe el podcast con ID {args.podcast}")
                sys.exit(1)
            try:
                added = sync_podcast(p)
                print(f"\n🎉 {p.title}: {added} episodio(s) sincronizado(s).", flush=True)
            except Exception as e:
                print(f"❌ Error: {e}", flush=True)
                sys.exit(1)
    else:
        print(sync_all())