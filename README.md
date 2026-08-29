# Antares Bridge

Puente de sincronización entre Antares (MySQL 8.0) y Agenda System.

## Instalación en Windows Server

### 1. Instalar Python 3.9+ (o el que prefieras)

Descarga el instalador de python.org y, al instalar, marca **"Add Python to PATH"**.

Abre una terminal nueva y verifica:

```
python --version
```

> Nota: la carpeta `wheels/` contiene ruedas offline para Python 3.9 (`cp39`).
> Con internet, `pip` descarga la versión adecuada automáticamente.

### 2. Copiar el proyecto

Copia toda la carpeta del proyecto a la máquina (incluye `wheels/` para instalación offline).

### 3. Configurar .env

```
copy .env.example .env
notepad .env
```

Cambia `ANTARES_SERVER` por el host real de MySQL (p. ej. `127.0.0.1`),
`ANTARES_PORT` por el puerto (3306), `ANTARES_DATABASE` (p. ej. `datosipspymr`),
y las credenciales. También ajusta `AGENDA_SYSTEM_URL`.

### 5. Ejecutar

```
run.bat
```

**run.bat** se encarga de todo: crea el venv, instala dependencias (online o desde `wheels/` si no hay internet) y arranca el bridge.

Dashboard: `http://localhost:8001`

## Arranque automático y resistencia a fallos (Windows Server)

Para que el bridge sobreviva reinicios del servidor (cortes de electricidad) y
se recupere solo de fallos:

1. Ejecuta `run.bat` una vez para dejar el venv creado.
2. Ejecuta `install_service.bat` **como Administrador**.

Esto crea dos tareas programadas (visibles en `taskschd.msc`):

- **AntaresBridge**: corre como SYSTEM al arrancar Windows, sin necesidad de
  iniciar sesión, y se reinicia automáticamente cada 1 minuto si el proceso
  falla o muere.
- **AntaresBridgeWatchdog**: cada 5 minutos consulta
  `http://localhost:8001/api/status`; si no responde, reinicia el bridge
  (cubre cuelgues silenciosos). Deja rastro en `logs\watchdog.log`.

Para quitar el servicio: `uninstall_service.bat`.

> En la BIOS del servidor verifica `Restore on AC Power Loss = Power On`
> para que la máquina encienda sola al volver la electricidad.

> Los logs también se escriben en `logs\bridge.log` (rotación de 5 MB x 5),
> útil para diagnosticar caídas cuando no hay consola.

## Desarrollo local (macOS/Linux)

```bash
./run.sh
```

o con Docker:

```bash
docker compose up --build -d
```

> Con Docker, apunta `ANTARES_SERVER` a `host.docker.internal` para llegar al MySQL de la máquina anfitriona.
