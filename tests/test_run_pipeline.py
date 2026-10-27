
import argparse

import pytest

from run_pipeline import positive_int


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", 1),
        ("39", 39),
        ("2023", 2023),
    ],
)
def test_positive_int_accepts_valid_values(value, expected):
    assert positive_int(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "abc",
        "1.5",
        "",
    ],
)
def test_positive_int_rejects_invalid_values(value):
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int(value)
