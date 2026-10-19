"""Unit config + status (SyncStatus) — 100% puro sin DB."""
import pytest

from src.config import Settings, get_settings
from src.db.status import SyncStatus


def test_empty_env_to_default():
    s = Settings(antares_server="", antares_port=3306, antares_database="x", antares_user="u", antares_password="p", agenda_system_url="http://a", sync_api_key="k")
    # empty string debe caer al default 127.0.0.1
    assert s.antares_server == "127.0.0.1"


def test_get_settings_cache(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ANTARES_SERVER", "10.0.0.1")
    s = get_settings()
    assert s.antares_server == "10.0.0.1"
    get_settings.cache_clear()


def test_sync_status_record_and_to_dict():
    st = SyncStatus()
    st.record_operation("fetch_services", success=True, records_processed=37, duration_ms=15)
    d = st.to_dict()
    assert "service" in d
    assert "mysql" in d
    assert "agenda" in d
    assert "operations" in d
    assert d["operations"]["fetch_services"]["records_processed"] == 37
    st.record_operation("fetch_services", success=False, records_processed=0, error_message="boom", duration_ms=5)
    assert st.operations["fetch_services"].success is False


def test_sync_status_cycle_history_clipping():
    st = SyncStatus()
    for i in range(25):
        st.record_cycle_complete(duration_s=1.0, failed_ops=0, success_ops=7)
    assert len(st._cycle_history) == 20
    assert st.to_dict()["cycle_history"][-1]["operations_success"] == 7


def test_sync_status_mysql_ping():
    st = SyncStatus()
    st.record_mysql_ping(success=True, latency_ms=15)
    assert st.mysql_connected is True
    st.record_mysql_ping(success=False, latency_ms=0, error="timeout")
    assert st.mysql_connected is False
