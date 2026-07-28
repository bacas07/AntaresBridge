# Antares Bridge

Puente de sincronización entre Antares (MySQL) y Agenda System.

## Instalación en Windows Server 2012 (on-premise)

### 1. Instalar Python 3.9

WS2012 solo soporta hasta Python 3.9. Descarga el instalador:

```
https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe
```

Al instalar, marca **"Add Python 3.9 to PATH"** y haz clic en **Install Now**.

Abre una terminal cmd nueva y verifica:

```
python --version
```

### 2. Copiar el proyecto

Copia toda la carpeta del proyecto a la máquina (incluye `wheels/` para instalación offline).

### 3. Configurar .env

```
copy .env.example .env
notepad .env
```

Cambia `ANTARES_SERVER` por la IP real del MySQL y `AGENDA_SYSTEM_URL` por la URL del sistema de agenda.

### 4. Ejecutar

```
python run.py
```

**run.py** se encarga de todo: crea el venv, instala dependencias (online o desde `wheels/` si no hay internet) y arranca el bridge.

Dashboard: `http://localhost:8001`

## Desarrollo local (macOS/Linux con Docker)

```bash
docker compose up --build -d
```
