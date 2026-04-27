import pytest
from rest_framework.test import APIClient

from accounts.tests.factories import EligibleBrokerUserFactory, UserFactory


@pytest.fixture(autouse=True)
def test_media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def broker_user(db):
    return EligibleBrokerUserFactory(email="broker@example.com")


@pytest.fixture
def buyer_user(db):
    return UserFactory(email="buyer@example.com")


@pytest.fixture
def seller_user(db):
    return UserFactory(email="seller@example.com")


@pytest.fixture
def authenticated_broker_client(api_client, broker_user):
    api_client.force_authenticate(user=broker_user)
    return api_client
