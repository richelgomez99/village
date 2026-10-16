import os

# Tests never touch shared cloud state: no real dials, no Surreal Cloud wipe on reset_demo, no Agent Memory writes.
os.environ.setdefault("VILLAGE_DIALER", "fake")
os.environ["SURREAL_DB_URL"] = ""
os.environ.setdefault("VILLAGE_MEMORY", "off")
