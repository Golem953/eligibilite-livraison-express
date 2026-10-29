from __future__ import annotations

import copy


class FakeMongoCollection:
    """Collection MongoDB factice : les seules requêtes de `MongoOrderRepository`, sans serveur.

    Filtres pris en charge : égalité (`{"order_id": "CMD-1"}`) et `$in`.
    """

    def __init__(self, documents: list[dict] | None = None):
        self.documents: list[dict] = [copy.deepcopy(document) for document in documents or []]

    def replace_one(self, filter: dict, document: dict, upsert: bool = False) -> None:
        for index, existing in enumerate(self.documents):
            if _matches(existing, filter):
                self.documents[index] = copy.deepcopy(document)
                return
        if upsert:
            self.documents.append(copy.deepcopy(document))

    def find_one(self, filter: dict, projection: dict | None = None) -> dict | None:
        return next(iter(self.find(filter, projection)), None)

    def find(self, filter: dict, projection: dict | None = None) -> _FakeCursor:
        excluded = {key for key, value in (projection or {}).items() if value == 0}
        return _FakeCursor([
            {key: value for key, value in document.items() if key not in excluded}
            for document in self.documents
            if _matches(document, filter)
        ])


class _FakeCursor(list):
    def sort(self, key: str, direction: int = 1) -> _FakeCursor:
        return _FakeCursor(sorted(self, key=lambda document: document[key], reverse=direction < 0))


def _matches(document: dict, filter: dict) -> bool:
    for key, condition in filter.items():
        if isinstance(condition, dict):
            if key not in document or document[key] not in condition["$in"]:
                return False
        elif document.get(key) != condition:
            return False
    return True
