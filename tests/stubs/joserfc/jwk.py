class OctKey:
    """Minimal symmetric key wrapper."""

    @classmethod
    def import_key(cls, key: str) -> "OctKey":
        return cls()
