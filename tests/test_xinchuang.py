import pytest
from code_adapt.models import Repository

class TestXinchuangField:
    def test_default_is_none(self):
        repo = Repository(name="test", url="https://github.com/test/test", type="upstream")
        assert repo.xinchuang_compatible is None

    def test_set_true(self):
        repo = Repository(name="test", url="https://github.com/test/test", type="upstream", xinchuang_compatible=True)
        assert repo.xinchuang_compatible is True

    def test_set_false(self):
        repo = Repository(name="test", url="https://github.com/test/test", type="upstream", xinchuang_compatible=False)
        assert repo.xinchuang_compatible is False

    def test_serialization(self):
        repo = Repository(name="test", url="https://github.com/test/test", type="upstream", xinchuang_compatible=True)
        data = repo.model_dump()
        assert data["xinchuang_compatible"] is True

    def test_backward_compat(self):
        data = {"name": "test", "url": "https://github.com/test/test", "type": "upstream"}
        repo = Repository.model_validate(data)
        assert repo.xinchuang_compatible is None
