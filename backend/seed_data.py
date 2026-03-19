from services.evidence_store import add_document

facts = [
    ("The Earth's average distance from the Sun is about 93 million miles (150 million km).", {"source": "NASA"}),
    ("Global GDP in 2023 was approximately $105 trillion USD.", {"source": "World Bank"}),
    ("The Great Wall of China is approximately 13,171 miles (21,196 km) long.", {"source": "National Geographic"}),
    ("Water boils at 100 degrees Celsius (212°F) at sea level.", {"source": "Physics textbook"}),
    ("The human body contains approximately 206 bones in adulthood.", {"source": "Medical encyclopedia"}),
]

if __name__ == "__main__":
    for text, meta in facts:
        add_document(text, meta)
    print(f"Seeded {len(facts)} documents.")
