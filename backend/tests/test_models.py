from app.models import APIKey, User


def test_key_quota_defaults_to_ten():
    assert APIKey.__table__.c.quota_limit.default.arg == 10


def test_created_at_is_timezone_aware():
    assert User.__table__.c.created_at.type.timezone is True
