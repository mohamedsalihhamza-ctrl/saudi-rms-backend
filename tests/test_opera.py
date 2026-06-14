import pytest
from datetime import date
from app.integrations.pms.opera_cloud import OperaConfig, OperaLiveAvailability


def test_opera_config_defaults():
    config = OperaConfig(
        client_id="test-id",
        client_secret="test-secret",
        property_code="PROP1",
    )
    assert config.base_url == "https://api-rsr.opera-api.com"
    assert config.timeout_seconds == 30


def test_oper_live_availability():
    avail = OperaLiveAvailability(
        date=date(2026, 6, 15),
        total_rooms=100,
        available_rooms=72,
        out_of_order=3,
        occupancy_pct=28.0,
    )
    assert avail.total_rooms == 100
    assert avail.occupancy_pct == 28.0
    assert avail.available_rooms == 72


def test_reservation_dataclass():
    from app.integrations.pms.opera_cloud import Reservation

    res = Reservation(
        external_id="RES123",
        room_type_code="DLX",
        check_in=date(2026, 6, 15),
        check_out=date(2026, 6, 17),
        booking_rate=450.00,
        currency="SAR",
        guest_name="Ahmed",
    )
    assert res.external_id == "RES123"
    assert res.booking_rate == 450.00
    assert res.currency == "SAR"
