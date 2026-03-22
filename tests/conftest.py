import pytest
from app.core.apartment import Apartment, ApartmentFilter
from app.core.enums import SocialStatus


def make_filter(**kwargs) -> ApartmentFilter:
    defaults = dict(
        min_rooms=1,
        max_rooms=3,
        min_sqm=20,
        max_sqm=80,
        min_price=200,
        max_price=1000,
        social_status=SocialStatus.ANY,
    )
    return ApartmentFilter(**{**defaults, **kwargs})


def make_apartment(**kwargs) -> Apartment:
    defaults = dict(
        id="degewo:123",
        source="Degewo",
        url="https://example.com/apt/123",
        title="Test Wohnung",
        price=600.0,
        rooms=2.0,
        sqm=50.0,
        social_status=SocialStatus.ANY,
    )
    return Apartment(**{**defaults, **kwargs})


@pytest.fixture
def complete_filter() -> ApartmentFilter:
    return make_filter()


@pytest.fixture
def incomplete_filter() -> ApartmentFilter:
    return ApartmentFilter(
        min_rooms=None,
        max_rooms=None,
        min_sqm=None,
        max_sqm=None,
        min_price=None,
        max_price=None,
        social_status=SocialStatus.ANY,
    )


@pytest.fixture
def basic_apartment() -> Apartment:
    return make_apartment()
