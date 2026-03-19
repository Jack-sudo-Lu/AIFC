import chromadb
from pathlib import Path

DB_PATH = str(Path(__file__).parent.parent / "chroma_db")

client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection("evidence")


def add_document(text: str, metadata: dict = None):
    doc_id = str(collection.count())
    collection.add(documents=[text], metadatas=[metadata or {}], ids=[doc_id])


# Auto-seed on import (only if empty)
if collection.count() == 0:
    _facts = [
        ("The Earth's average distance from the Sun is about 93 million miles (150 million km).", {"source": "NASA"}),
        ("Global GDP in 2023 was approximately $105 trillion USD.", {"source": "World Bank"}),
        ("The Great Wall of China is approximately 13,171 miles (21,196 km) long.", {"source": "National Geographic"}),
        ("Water boils at 100 degrees Celsius (212°F) at sea level.", {"source": "Physics textbook"}),
        ("The human body contains approximately 206 bones in adulthood.", {"source": "Medical encyclopedia"}),
    ]
    for text, meta in _facts:
        add_document(text, meta)


def retrieve_evidence(query: str, top_k: int = 3) -> list[dict]:
    results = collection.query(query_texts=[query], n_results=top_k)
    return [
        {"text": doc, "metadata": meta}
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]
