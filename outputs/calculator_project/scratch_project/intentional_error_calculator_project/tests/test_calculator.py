import pytest

from calculator import add, divide, multiply


def test_adds_numbers():
    assert add(2, 3) == 5
    assert add(-4, 10) == 6


def test_multiplies_numbers():
    assert multiply(4, 5) == 20
    assert multiply(-3, 2) == -6


def test_divides_numbers():
    assert divide(10, 2) == 5
    assert divide(9, 3) == 3


def test_divide_by_zero_raises():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)
