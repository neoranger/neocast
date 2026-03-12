# Usamos una imagen oficial y ligera de Python
FROM python:3.11-slim

# Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# 👇 Instalamos FFmpeg en el contenedor de Linux 👇
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copiamos el archivo de dependencias primero (para aprovechar el caché de Docker)
COPY requirements.txt .

# Instalamos las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código al contenedor
COPY . .

# Exponemos el puerto 5000 que usa Flask
EXPOSE 5000

# Comando para iniciar la aplicación
CMD ["python", "app.py"]
