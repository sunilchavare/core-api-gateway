import pytest
from pydantic import ValidationError

from app.schemas import UserLoginRequest, UserRegisterRequest


def test_username_whitespace_is_stripped():
    request = UserRegisterRequest(username="  bob_smith  ", password="TestPass123!")

    assert request.username == "bob_smith"


def test_whitespace_only_username_is_rejected():
    with pytest.raises(ValidationError):
        UserRegisterRequest(username="     ", password="TestPass123!")


def test_login_username_is_stripped_too():
    assert UserLoginRequest(username=" bob_smith ", password="x").username == "bob_smith"


def test_password_of_72_bytes_is_accepted():
    UserRegisterRequest(username="bob_smith", password="a" * 72)


def test_password_over_72_bytes_is_rejected():
    with pytest.raises(ValidationError):
        UserRegisterRequest(username="bob_smith", password="a" * 73)


def test_multibyte_password_is_measured_in_bytes_not_characters():
    # 40 characters, but 80 bytes in UTF-8.
    with pytest.raises(ValidationError):
        UserRegisterRequest(username="bob_smith", password="é" * 40)
