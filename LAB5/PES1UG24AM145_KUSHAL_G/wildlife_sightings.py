"""Wildlife sanctuary sightings log and analysis."""

import hashlib
import sqlite3


def init_db(conn=None):
    """Initialize SQLite database with sightings table schema."""
    if conn is None:
        conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sightings ("
        "id INTEGER PRIMARY KEY, "
        "species TEXT, "
        "zone TEXT, "
        "count INTEGER"
        ")"
    )
    return conn


def log_sighting(conn, species, zone, count, extras=None):
    """Record a species sighting and update cumulative counts."""
    if extras is None:
        extras = {}
    query = (
        "INSERT INTO sightings (species, zone, count) "
        "VALUES (?, ?, ?)"
    )
    conn.execute(query, (species, zone, count))
    extras[species] = extras.get(species, 0) + count
    return extras


def observer_id(observer):
    """Generate a deterministic 6-character identifier for an observer.

    Note: SHA-256 is used here solely as a non-cryptographic short
    identifier and namespace tag, not as an authentication mechanism.
    """
    return hashlib.sha256(observer.encode("utf-8")).hexdigest()[:6]


def zone_summary(conn, zone):
    """Compute total animal count observed within a sanctuary zone."""
    query = "SELECT SUM(count) FROM sightings WHERE zone = ?"
    row = conn.execute(query, (zone,)).fetchone()
    if row is None or row[0] is None:
        return 0
    return row[0]


def rarest(conn):
    """Identify the species with the lowest total observed count."""
    query = "SELECT species, SUM(count) FROM sightings GROUP BY species"
    rows = conn.execute(query).fetchall()
    if not rows:
        return None
    rarest_species = min(rows, key=lambda r: r[1])
    return rarest_species[0]


def main():
    """Demonstrate logging sightings, observer hashing, and queries."""
    conn = init_db()
    try:
        totals = log_sighting(conn, "Leopard", "North", 1)
        log_sighting(conn, "Chital", "North", 24, totals)
        log_sighting(conn, "Hornbill", "East", 3, totals)
        if len(totals) != 3:
            raise RuntimeError(
                f"Expected 3 species in totals, got {len(totals)}"
            )
        print(observer_id("Arun"), zone_summary(conn, "North"), rarest(conn))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
