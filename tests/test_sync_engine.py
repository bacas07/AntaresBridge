"""SyncEngine — unit con mocks de MySQL y httpx."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.sync.engine import SyncEngine, serialize_row, validate_environment
from src.config import get_settings


def test_validate_environment_ok(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ANTARES_SERVER", "127.0.0.1")
    monkeypatch.setenv("ANTARES_PORT", "3306")
    monkeypatch.setenv("ANTARES_DATABASE", "datosipspymr")
    monkeypatch.setenv("ANTARES_USER", "agenda")
    monkeypatch.setenv("ANTARES_PASSWORD", "x")
    monkeypatch.setenv("AGENDA_SYSTEM_URL", "http://a:8000")
    monkeypatch.setenv("SYNC_API_KEY", "k")
    assert validate_environment() is True
    get_settings.cache_clear()


def test_validate_environment_missing(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ANTARES_SERVER", "")
    # force default fallback still counts as present, so we patch Settings directly
    with patch("src.sync.engine.get_settings") as mock:
        m = MagicMock()
        m.antares_server = ""
        m.antares_port = 0
        m.antares_database = ""
        m.antares_user = ""
        m.antares_password = ""
        m.agenda_system_url = ""
        m.sync_api_key = ""
        mock.return_value = m
        with pytest.raises(RuntimeError):
            validate_environment()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_sync_cycle_success_with_mocks():
    eng = SyncEngine()
    # mock DB fetches
    with patch("src.sync.engine.antares_db") as mock_db, patch.object(eng, "_get_client") as mock_client:
        mock_db.fetch_services.return_value = [{"code": "890283", "name": "Pediatria"}]
        mock_db.fetch_doctors.return_value = [{"id": "17953649", "name": "Jorge"}]
        mock_db.fetch_schedules.return_value = [{"doctor_id": "17953649", "day_of_week": 1, "start_time": "08:00:00", "end_time": "12:00:00", "slot_duration": 20, "is_active": True}]
        mock_db.fetch_unavailability.return_value = []
        mock_db.fetch_plan_limits.return_value = []
        mock_db.fetch_patients.return_value = []
        mock_db.fetch_new_appointments.return_value = []

        mock_http = AsyncMock()
        mock_resp = MagicMock(status_code=200, raise_for_status=lambda: None)
        mock_http.post = AsyncMock(return_value=mock_resp)
        mock_http.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {"appointments": []}))
        mock_client.return_value = mock_http

        await eng.sync_cycle()
        # al menos 3 posts debieron ocurrir (services, doctors, schedules)
        assert mock_http.post.await_count >= 3
        await eng.close()


@pytest.mark.asyncio
async def test_wait_for_mysql_with_backoff(monkeypatch):
    from src.sync.engine import wait_for_mysql_with_backoff
    from unittest.mock import patch
    import asyncio

    with patch("src.sync.engine.antares_db") as mock_db, patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_db.ping.side_effect = [(False, 0, "timeout"), (True, 15, "")]
        # debe reintentar una vez y salir
        await wait_for_mysql_with_backoff()
        assert mock_db.ping.call_count == 2
        mock_sleep.assert_awaited_once()
