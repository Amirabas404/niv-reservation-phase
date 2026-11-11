from app.integrations.storage import PrivateStorage, get_storage


def storage_for_reports() -> PrivateStorage:
    return get_storage()
