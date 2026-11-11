import pytest

from app.integrations.storage import ALLOWED_RECEIPT_TYPES, LocalPrivateStorage, new_receipt_key


def test_receipt_keys_are_namespaced_and_typed():
    key = new_receipt_key("image/png")
    assert key.startswith("receipts/") and key.endswith(".png")


@pytest.mark.asyncio
async def test_local_storage_round_trip_and_path_guard(tmp_path):
    store = LocalPrivateStorage(str(tmp_path))
    key = await store.save(b"abc", "image/jpeg")
    assert await store.read(key) == b"abc"
    with pytest.raises(ValueError):
        await store.read("../escape.txt")
    assert "image/jpeg" in ALLOWED_RECEIPT_TYPES
