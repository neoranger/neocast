# 🎙️ NeoCast

NeoCast es una plataforma ligera y autoalojada (*self-hosted*) para la gestión y publicación de podcasts. Diseñada con una filosofía minimalista y enfocada en la eficiencia, es ideal para correr en servidores domésticos (homelabs) con bajos recursos sin sacrificar funcionalidades profesionales.

## ✨ Características Principales

* **Panel de Administración Seguro:** Gestión de episodios protegida por Autenticación de Dos Factores (2FA - TOTP) nativa.
* **Ultra Ligero:** Construido en Python con Flask, optimizado para consumir la menor cantidad de RAM posible.
* **Gestión Multimedia Local:** Subida, alojamiento y distribución directa de tus archivos de audio sin intermediarios.
* **Listo para Docker:** Despliegue estandarizado y rápido mediante contenedores, ideal para convivir con proxys inversos.

## 🛠️ Tecnologías Utilizadas

* **Backend:** Python 3 + Flask
* **Seguridad:** PyOTP & qrcode (Generación y validación de tokens 2FA)
* **Frontend:** HTML5, CSS (Modo Oscuro nativo), Jinja2
* **Infraestructura:** Docker & Docker Compose

## 🚀 Instalación y Despliegue

### Prerrequisitos
* [Docker](https://docs.docker.com/get-docker/) y [Docker Compose](https://docs.docker.com/compose/install/) instalados en el servidor.
* Un proxy inverso (como Nginx Proxy Manager o Traefik) recomendado para gestionar los certificados SSL (HTTPS).

### Paso a Paso

1. **Clonar el repositorio:**
   ```
   git clone [https://github.com/tu_usuario/NeoCast.git](https://github.com/tu_usuario/NeoCast.git)
   ```
   ```cd NeoCast```
2. **Configuración inicial:**
   Asegúrate de configurar tus variables de entorno, puertos o volúmenes en el archivo docker-compose.yml según las necesidades de tu servidor. (Nota: Por seguridad, los audios y bases de datos locales están ignorados en el control de versiones).
3. **Levantar el servicio**
   Construye la imagen y levanta el contenedor en segundo plano con un solo comando:
   ```docker-compose up -d --build```
4. **Acceso al Panel:**
   Una vez que el contenedor esté corriendo, accede mediante tu proxy inverso o directamente a la IP local y puerto configurado.
   
## 🔒 Sobre la Seguridad (2FA)
Para proteger la gestión de los episodios, NeoCast requiere Autenticación de Dos Pasos.
Durante el primer inicio de sesión exitoso con tus credenciales de administrador, el sistema generará un código QR único. Escanéalo con tu aplicación de preferencia (Google Authenticator, Authy, Aegis, etc.) para vincular el dispositivo. A partir de ese momento, se requerirá el token temporal de 6 dígitos para acceder al panel.

## 🤝 Contribuciones
Este proyecto nació como una solución personal para retomar el control de los datos y simplificar el self-hosting. Siéntete libre de hacer un fork, abrir issues o enviar pull requests si encuentras áreas de mejora.
