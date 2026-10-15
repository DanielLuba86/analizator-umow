from app.security.passwords import hash_password, verify_password


def test_password_roundtrip() -> None:
    h = hash_password("sekret-123")
    assert h != "sekret-123"
    assert verify_password(h, "sekret-123") is True


def test_wrong_password_and_invalid_hash() -> None:
    h = hash_password("sekret-123")
    assert verify_password(h, "inne") is False
    assert verify_password("to-nie-hash", "sekret-123") is False
