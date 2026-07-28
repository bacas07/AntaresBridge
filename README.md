# Antares Bridge

Puente de sincronización entre Antares (MySQL) y Agenda System.

- Consulta servicios, doctores, horarios, citas, pacientes, etc. en Antares cada N minutos
- Envía datos nuevos/actualizados a Agenda System
- Recibe cambios locales de Agenda System y los escribe en Antares

## Requisitos

- Python 3.8+
- Acceso a la base de datos MySQL de Antares
- Agenda System corriendo y accesible

## Configuración

```bash
cp .env.example .env
# Editar .env con las credenciales y URLs correctas
```

## Ejecución (sin Docker)

```bash
./run.sh
```

El script crea automáticamente el entorno virtual, instala las dependencias e inicia el bridge.

El dashboard de monitoreo estará disponible en `http://localhost:8001`.

## Ejecución (con Docker)

```bash
docker compose up --build -d
```

## Logs

```bash
# Sin Docker: los logs se imprimen en stdout
# Con Docker:
docker compose logs -f
```
