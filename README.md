# Antares Bridge

Puente de sincronización entre Antares (SQL Server legacy) y Agenda System.

- Corre en red privada (sin puertos expuestos)
- Consulta CIT, AFI, MED, SER en Antares cada N minutos
- Envía datos nuevos/actualizados a Agenda System
- Recibe cambios locales de Agenda System y los escribe en Antares

## Arquitectura

```
Antares SQL Server (1433)
        ↕
  antares-bridge (sync engine)
        ↕  HTTP outbound
Agenda System (8000)
```

## Requisitos

- Docker & Docker Compose
- Acceso a SQL Server Antares (host.docker.internal:1433)
- Agenda System corriendo y accesible

## Configuración

```bash
cp .env.example .env
# Editar .env con credenciales de Antares
```

## Ejecución

```bash
docker compose up --build -d
```

## Logs

```bash
docker compose logs -f
```
