import pytest

from ppcm.context import Context


@pytest.fixture(scope="session")
def ctx() -> Context:
    return Context.load()
