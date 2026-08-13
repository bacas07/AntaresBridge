# Antares Bridge

Puente de sincronización entre Antares (SQL Server) y Agenda System.

## Instalación en Windows Server

### 1. Instalar Python 3.9+ (o el que prefieras)

Descarga el instalador de python.org y, al instalar, marca **"Add Python to PATH"**.

Abre una terminal nueva y verifica:

```
python --version
```

> Nota: la carpeta `wheels/` contiene ruedas offline para Python 3.9 (`cp39`).
> Con internet, `pip` descarga la versión adecuada automáticamente.

### 2. Instalar el ODBC Driver for SQL Server

`pyodbc` necesita el driver de Microsoft:

```
https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
```

Instala el **ODBC Driver 17 o 18 for SQL Server** (suficiente con el instalador estándar).

### 3. Copiar el proyecto

Copia toda la carpeta del proyecto a la máquina (incluye `wheels/` para instalación offline).

### 4. Configurar .env

```
copy .env.example .env
notepad .env
```

Cambia `ANTARES_SERVER` por el host real de SQL Server (p. ej. `localhost`),
`ANTARES_PORT` por el puerto (1433), `ANTARES_DATABASE` (p. ej. `PastorYMaria`),
y las credenciales. También ajusta `AGENDA_SYSTEM_URL`.

### 5. Ejecutar

```
run.bat
```

**run.bat** se encarga de todo: crea el venv, instala dependencias (online o desde `wheels/` si no hay internet) y arranca el bridge.

Dashboard: `http://localhost:8001`

## Desarrollo local (macOS/Linux)

```bash
./run.sh
```

o con Docker:

```bash
docker compose up --build -d
```

> Con Docker, apunta `ANTARES_SERVER` a `host.docker.internal` para llegar al SQL Server de la máquina anfitriona.
