"""A contract test for LangGraph stores (Lesson 08.07).

``check_store_contract(store)`` runs the behaviours graph code relies on and returns
``{check: True/False}``. Run it against every store you might use (``InMemoryStore``,
``SqliteStore``, a Postgres store, your own ``BaseStore`` subclass) before you swap one
for another: same calls, same results. ``semantic=True`` also checks vector search
(the store needs an index; with ``HashingEmbeddings`` "shared words" count as similar).
"""

from __future__ import annotations

from typing import Any

__all__ = ["check_store_contract"]


def check_store_contract(store: Any, *, namespace: tuple[str, ...] = ("contract", "u1"),
                         semantic: bool = False) -> dict[str, bool]:
    """Exercise ``put/get/search/delete/list_namespaces`` and report which behaviours hold."""
    other = (*namespace[:-1], namespace[-1] + "-other")
    results: dict[str, bool] = {}
    store.put(namespace, "pref", {"text": "short sentences, no jargon"})
    store.put(namespace, "tone", {"text": "friendly but direct"})
    store.put(other, "pref", {"text": "long sentences"})

    item = store.get(namespace, "pref")
    results["get returns the value"] = item is not None and item.value == {"text": "short sentences, no jargon"}
    results["get has key and namespace"] = item is not None and item.key == "pref" and tuple(item.namespace) == namespace
    results["missing key → None"] = store.get(namespace, "nope") is None

    store.put(namespace, "pref", {"text": "very short sentences"})
    results["put overwrites"] = store.get(namespace, "pref").value["text"] == "very short sentences"

    listed = {i.key for i in store.search(namespace)}
    results["search lists one namespace only"] = listed == {"pref", "tone"}
    results["search(filter=) matches values"] = [i.key for i in store.search(namespace, filter={"text": "friendly but direct"})] == ["tone"]
    results["prefix search sees both users"] = {tuple(i.namespace) for i in store.search(namespace[:-1])} >= {namespace, other}
    results["list_namespaces"] = set(map(tuple, store.list_namespaces(prefix=namespace[:-1]))) >= {namespace, other}

    if semantic:
        hits = store.search(namespace, query="friendly direct tone", limit=1)
        results["semantic search ranks by meaning/words"] = bool(hits) and hits[0].key == "tone" and hits[0].score is not None

    store.delete(namespace, "tone")
    results["delete removes"] = store.get(namespace, "tone") is None
    for ns, key in ((namespace, "pref"), (other, "pref")):     # leave the store clean
        store.delete(ns, key)
    results["cleanup leaves nothing"] = not list(store.search(namespace[:-1]))
    return results
