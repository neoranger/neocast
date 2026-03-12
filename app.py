import os
import math
import email.utils
import time
import subprocess
import sys
import pyotp
import qrcode
import base64
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import make_response
from flask import send_from_directory
from io import BytesIO
from functools import wraps
from flask import session

# --- CONFIGURACIÓN DE CARPETAS ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
MEDIA_DIR = os.path.join(BASE_DIR, 'static', 'media')

for folder in [DATA_DIR, MEDIA_DIR]:
    if not os.path.exists(folder):
        os.makedirs(folder)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(DATA_DIR, 'neocast.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'super-secreto-cambiar-luego'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # Límite de 200MB por MP3

# Esto le dice a Flask que confíe en los headers HTTP_X_FORWARDED_PROTO
app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

# --- CONFIGURACIÓN DE SEGURIDAD ---
TOTP_FILE = os.path.join(DATA_DIR, '.totp_secret')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# El "Guardia de Seguridad" (Decorador)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

db = SQLAlchemy(app)

# --- MODELOS DE LA BASE DE DATOS ---
class Podcast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100))
    cover_image = db.Column(db.String(255))
    episodes = db.relationship('Episode', backref='podcast', lazy=True, cascade="all, delete-orphan", order_by="desc(Episode.pub_date)")

class Episode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    podcast_id = db.Column(db.Integer, db.ForeignKey('podcast.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text)
    audio_file = db.Column(db.String(255), nullable=False)
    duration = db.Column(db.String(10)) 
    byte_size = db.Column(db.Integer)   
    pub_date = db.Column(db.DateTime, default=datetime.utcnow)
    listens = db.Column(db.Integer, default=0)

with app.app_context():
    db.create_all()

# --- FUNCIONES AUXILIARES ---
def slugify(text):
    import re
    text = text.lower()
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')

# --- FILTROS DE PLANTILLA ---
# Los RSS requieren un formato de fecha súper específico llamado RFC-2822 (Ej: Wed, 02 Oct 2025 08:00:00 -0000)
def format_rfc2822(dt):
    return email.utils.formatdate(time.mktime(dt.timetuple()))

# Inyectamos esta función a Jinja para poder usarla en el XML
app.jinja_env.filters['rfc2822'] = format_rfc2822

# --- RUTA DEL MOTOR RSS ---
@app.route('/podcast/<slug>/feed.xml')
def podcast_feed(slug):
    # Buscamos el podcast por su slug (el nombre en la URL)
    podcast = Podcast.query.filter_by(slug=slug).first_or_404()
    
    # Capturamos el email del entorno (o usamos uno por defecto por las dudas)
    podcast_email = os.environ.get('PODCAST_EMAIL', 'podcast@midominio.com')

    # Renderizamos la plantilla XML
    xml_content = render_template('feed.xml', podcast=podcast, email=podcast_email, request=request)
    
    # Preparamos la respuesta indicándole al navegador que esto es un archivo XML, no HTML
    response = make_response(xml_content)
    response.headers['Content-Type'] = 'application/rss+xml; charset=utf-8'
    return response

# --- RUTAS PÚBLICAS ---
@app.route('/')
def index():
    podcasts = Podcast.query.all()
    return render_template('index.html', podcasts=podcasts)

# --- RUTAS DEL REPRODUCTOR WEB ---
@app.route('/podcast/<slug>')
def podcast_detail(slug):
    # Página principal de un podcast específico
    podcast = Podcast.query.filter_by(slug=slug).first_or_404()
    return render_template('podcast.html', podcast=podcast)

@app.route('/podcast/<podcast_slug>/<episode_slug>')
def episode_detail(podcast_slug, episode_slug):
    # Página de un episodio específico
    podcast = Podcast.query.filter_by(slug=podcast_slug).first_or_404()
    episode = Episode.query.filter_by(podcast_id=podcast.id, slug=episode_slug).first_or_404()
    return render_template('episode.html', podcast=podcast, episode=episode)
    
# --- RUTA PARA EL REPRODUCTOR EMBEBIDO (IFRAME) ---
@app.route('/embed/episode/<int:episode_id>')
def embed_episode(episode_id):
    episode = Episode.query.get_or_404(episode_id)
    return render_template('embed.html', episode=episode, podcast=episode.podcast)

# --- RUTAS DE ADMINISTRACIÓN ---
@app.route('/admin')
@login_required
def admin_dashboard():
    podcasts = Podcast.query.all()
    return render_template('admin.html', podcasts=podcasts)

@app.route('/admin/podcast/new', methods=['GET', 'POST'])
@login_required
def new_podcast():
    if request.method == 'POST':
        title = request.form['title']
        cover_file = request.files.get('cover_image')
        cover_filename = None

        # Si suben una portada, la guardamos con nombre único
        if cover_file and cover_file.filename.endswith(('.png', '.jpg', '.jpeg')):
            timestamp = int(time.time())
            cover_filename = secure_filename(f"cover_{timestamp}_{cover_file.filename}")
            cover_filepath = os.path.join(MEDIA_DIR, cover_filename)
            cover_file.save(cover_filepath)

        new_pod = Podcast(
            title=title,
            slug=slugify(title),
            description=request.form['description'],
            author=request.form['author'],
            category=request.form['category'],
            cover_image=cover_filename # Guardamos el nombre en la DB
        )
        db.session.add(new_pod)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('form_podcast.html')

@app.route('/admin/podcast/<int:podcast_id>/episode/new', methods=['GET', 'POST'])
@login_required
def new_episode(podcast_id):
    podcast = Podcast.query.get_or_404(podcast_id)
    
    if request.method == 'POST':
        title = request.form['title']
        audio_file = request.files['audio_file']
        
        if audio_file and audio_file.filename.endswith('.mp3'):
            # 1. Guardar el archivo físicamente
            timestamp = int(time.time()) # Genera un número único basado en la hora
            filename = secure_filename(f"{timestamp}_{slugify(title)}.mp3")
            filepath = os.path.join(MEDIA_DIR, filename)
            audio_file.save(filepath)
            
            # 2. Calcular Peso en Bytes
            byte_size = os.path.getsize(filepath)
            
            # 3. Leer la duración exacta con FFmpeg (a prueba de fallos VBR)
            try:
                # ffprobe analiza el archivo y devuelve los segundos exactos
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', filepath],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                total_seconds = float(result.stdout.strip())
                hours = int(total_seconds // 3600)
                mins = int((total_seconds % 3600) // 60)
                secs = int(total_seconds % 60)
                duration_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
            except Exception as e:
                # Fallback por si acaso
                duration_str = "00:00:00"
                print(f"Error calculando duración: {e}")
            
            # 4. Guardar en Base de Datos
            new_ep = Episode(
                podcast_id=podcast.id,
                title=title,
                slug=slugify(title),
                description=request.form['description'],
                audio_file=filename,
                duration=duration_str,
                byte_size=byte_size
            )
            db.session.add(new_ep)
            db.session.commit()
            return redirect(url_for('admin_dashboard'))
            
    return render_template('form_episode.html', podcast=podcast)
    
# --- RUTA PARA IMPORTAR RSS DESDE LA WEB ---
@app.route('/admin/import', methods=['GET', 'POST'])
@login_required
def admin_import():
    if request.method == 'POST':
        rss_url = request.form['rss_url']
        
        # Disparamos el script import_rss.py en segundo plano para no congelar la web
        # sys.executable es la ruta al Python actual dentro de Docker
        subprocess.Popen([sys.executable, 'import_rss.py', rss_url])
        
        # Redirigimos al usuario de inmediato al panel
        return redirect(url_for('admin_dashboard'))
        
    return render_template('form_import.html')
    
# --- RUTAS DE AUTENTICACIÓN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('admin_dashboard'))

    totp_secret = None
    first_time = False
    qr_b64 = None

    # Verificar si ya hay un secreto guardado
    if os.path.exists(TOTP_FILE):
        with open(TOTP_FILE, 'r') as f:
            totp_secret = f.read().strip()
    else:
        first_time = True
        if 'temp_secret' not in session:
            session['temp_secret'] = pyotp.random_base32()
        totp_secret = session['temp_secret']

    totp = pyotp.TOTP(totp_secret)

    if request.method == 'POST':
        password = request.form.get('password')
        code = request.form.get('code')

        # Verificamos contraseña Y código 2FA
        if password == ADMIN_PASSWORD and totp.verify(code):
            if first_time:
                # Guardamos el secreto permanentemente
                with open(TOTP_FILE, 'w') as f:
                    f.write(totp_secret)
                session.pop('temp_secret', None)
            
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Credenciales incorrectas o código expirado.", "error")

    # Generar QR si es primera vez
    if first_time:
        uri = totp.provisioning_uri(name='Admin', issuer_name='NeoCast')
        img = qrcode.make(uri)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    return render_template('login.html', first_time=first_time, qr_code=qr_b64)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))
    
# --- RUTAS DE BORRADO ---
@app.route('/admin/podcast/<int:podcast_id>/delete', methods=['POST'])
@login_required
def delete_podcast(podcast_id):
    podcast = Podcast.query.get_or_404(podcast_id)
    
    # 1. Borrar la imagen de portada física si existe
    if podcast.cover_image:
        cover_path = os.path.join(MEDIA_DIR, podcast.cover_image)
        if os.path.exists(cover_path):
            os.remove(cover_path)
            
    # 2. Borrar todos los archivos de audio asociados
    for ep in podcast.episodes:
        audio_path = os.path.join(MEDIA_DIR, ep.audio_file)
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
    # 3. Borrar de la base de datos (Cascade elimina los episodios automáticamente)
    db.session.delete(podcast)
    db.session.commit()
    flash(f"Podcast '{podcast.title}' eliminado por completo.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/episode/<int:episode_id>/delete', methods=['POST'])
@login_required
def delete_episode(episode_id):
    episode = Episode.query.get_or_404(episode_id)
    
    # 1. Borrar el archivo MP3 físico
    audio_path = os.path.join(MEDIA_DIR, episode.audio_file)
    if os.path.exists(audio_path):
        os.remove(audio_path)
        
    # 2. Borrar de la base de datos
    db.session.delete(episode)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))
    
# --- RUTAS DE EDICIÓN ---
@app.route('/admin/podcast/<int:podcast_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_podcast(podcast_id):
    podcast = Podcast.query.get_or_404(podcast_id)
    
    if request.method == 'POST':
        podcast.title = request.form['title']
        podcast.slug = request.form['slug']
        podcast.author = request.form['author']
        podcast.category = request.form['category']
        podcast.description = request.form['description']
        
        # Si suben una portada nueva, borramos la vieja y guardamos la nueva
        cover_file = request.files.get('cover_image')
        if cover_file and cover_file.filename.endswith(('.png', '.jpg', '.jpeg')):
            if podcast.cover_image:
                old_path = os.path.join(MEDIA_DIR, podcast.cover_image)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            unique_id = uuid.uuid4().hex[:8]
            cover_filename = secure_filename(f"cover_{unique_id}_{cover_file.filename}")
            cover_filepath = os.path.join(MEDIA_DIR, cover_filename)
            cover_file.save(cover_filepath)
            podcast.cover_image = cover_filename
            
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
        
    # Renderizamos el MISMO formulario, pero le pasamos el objeto podcast
    return render_template('form_podcast.html', podcast=podcast)

@app.route('/admin/episode/<int:episode_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_episode(episode_id):
    episode = Episode.query.get_or_404(episode_id)
    
    if request.method == 'POST':
        episode.title = request.form['title']
        episode.slug = request.form['slug']
        episode.description = request.form['description']
        
        # Opcional: Si deciden reemplazar el audio
        audio_file = request.files.get('audio_file')
        if audio_file and audio_file.filename.endswith('.mp3'):
            # 1. Borrar el audio viejo
            old_path = os.path.join(MEDIA_DIR, episode.audio_file)
            if os.path.exists(old_path):
                os.remove(old_path)
                
            # 2. Guardar el nuevo
            unique_id = uuid.uuid4().hex[:8]
            filename = secure_filename(f"ep_{unique_id}.mp3")
            filepath = os.path.join(MEDIA_DIR, filename)
            audio_file.save(filepath)
            
            # 3. Recalcular peso y duración con FFmpeg
            episode.byte_size = os.path.getsize(filepath)
            try:
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', filepath],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                )
                total_seconds = float(result.stdout.strip())
                hours = int(total_seconds // 3600)
                mins = int((total_seconds % 3600) // 60)
                secs = int(total_seconds % 60)
                episode.duration = f"{hours:02d}:{mins:02d}:{secs:02d}"
            except:
                pass
                
            episode.audio_file = filename

        db.session.commit()
        return redirect(url_for('admin_dashboard'))
        
    return render_template('form_episode.html', podcast=episode.podcast, episode=episode)

# --- RUTA DEDICADA PARA STREAMING DE AUDIO ---
@app.route('/media/<path:filename>')
def stream_audio(filename):
    # send_from_directory maneja nativamente las peticiones "Accept-Ranges" 
    # que necesitan los reproductores HTML5 para calcular la duración y avanzar el audio.
    return send_from_directory(MEDIA_DIR, filename)

# --- API PARA ESTADÍSTICAS ---
@app.route('/api/play/<int:episode_id>', methods=['POST'])
def register_play(episode_id):
    ep = Episode.query.get_or_404(episode_id)
    ep.listens += 1
    db.session.commit()
    return jsonify({'success': True, 'listens': ep.listens})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
