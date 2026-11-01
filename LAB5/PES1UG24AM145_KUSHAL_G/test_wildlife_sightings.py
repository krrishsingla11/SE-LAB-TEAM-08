"""Unit and regression tests for wildlife_sightings module."""

import hashlib
import io
import subprocess
import sys
import unittest

import wildlife_sightings


class TestWildlifeSightings(unittest.TestCase):
    """Test suite covering functionality, security, and edge cases."""

    def setUp(self):
        """Set up an isolated in-memory database before each test."""
        self.conn = wildlife_sightings.init_db()

    def tearDown(self):
        """Clean up and close database connection after each test."""
        self.conn.close()

    def test_1_normal_sighting_insertion_and_aggregation(self):
        """Verify normal sighting insertion and count tracking."""
        totals = wildlife_sightings.log_sighting(
            self.conn, "Leopard", "North", 1
        )
        wildlife_sightings.log_sighting(
            self.conn, "Chital", "North", 24, totals
        )
        wildlife_sightings.log_sighting(
            self.conn, "Hornbill", "East", 3, totals
        )

        self.assertEqual(len(totals), 3)
        self.assertEqual(totals["Leopard"], 1)
        self.assertEqual(totals["Chital"], 24)
        self.assertEqual(totals["Hornbill"], 3)

        self.assertEqual(
            wildlife_sightings.zone_summary(self.conn, "North"), 25
        )
        self.assertEqual(
            wildlife_sightings.zone_summary(self.conn, "East"), 3
        )
        self.assertEqual(wildlife_sightings.rarest(self.conn), "Leopard")

    def test_2_multiple_sightings_same_species(self):
        """Verify accumulation when the same species is logged repeatedly."""
        totals = wildlife_sightings.log_sighting(
            self.conn, "Tiger", "South", 2
        )
        wildlife_sightings.log_sighting(
            self.conn, "Tiger", "South", 3, totals
        )
        wildlife_sightings.log_sighting(
            self.conn, "Tiger", "North", 1, totals
        )

        self.assertEqual(totals["Tiger"], 6)
        self.assertEqual(
            wildlife_sightings.zone_summary(self.conn, "South"), 5
        )
        self.assertEqual(
            wildlife_sightings.zone_summary(self.conn, "North"), 1
        )
        self.assertEqual(wildlife_sightings.rarest(self.conn), "Tiger")

    def test_3_deterministic_observer_id(self):
        """Verify observer ID generation is deterministic and 6 characters."""
        expected_arun = hashlib.sha256("Arun".encode("utf-8")).hexdigest()[:6]
        id1 = wildlife_sightings.observer_id("Arun")
        id2 = wildlife_sightings.observer_id("Arun")

        self.assertEqual(len(id1), 6)
        self.assertEqual(id1, id2)
        self.assertEqual(id1, expected_arun)
        self.assertNotEqual(
            wildlife_sightings.observer_id("Arun"),
            wildlife_sightings.observer_id("Kushal"),
        )

    def test_4_sql_injection_payload_treated_as_literal(self):
        """Verify SQL injection payload is safely stored as literal text."""
        malicious_species = "Elephant'); DROP TABLE sightings;--"
        totals = wildlife_sightings.log_sighting(
            self.conn, malicious_species, "West", 2
        )

        self.assertIn(malicious_species, totals)
        cursor = self.conn.execute(
            "SELECT species, count FROM sightings WHERE zone = ?",
            ("West",),
        )
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], malicious_species)
        self.assertEqual(row[1], 2)

    def test_5_missing_zone_summary(self):
        """Verify zone_summary returns 0 for non-existent or empty zones."""
        summary = wildlife_sightings.zone_summary(self.conn, "UnknownZone")
        self.assertEqual(summary, 0)

    def test_6_empty_database_handling(self):
        """Verify rarest() returns None gracefully when no records exist."""
        result = wildlife_sightings.rarest(self.conn)
        self.assertIsNone(result)

    def test_7_import_does_not_execute_main(self):
        """Verify importing module does not execute demonstration prints."""
        cmd = [
            sys.executable,
            "-c",
            "import wildlife_sightings",
        ]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        self.assertEqual(proc.stdout.strip(), "")
        self.assertEqual(proc.stderr.strip(), "")

    def test_8_proper_connection_cleanup(self):
        """Verify main() runs and properly manages its resources."""
        saved_stdout = sys.stdout
        try:
            sys.stdout = io.StringIO()
            wildlife_sightings.main()
            output = sys.stdout.getvalue().strip()
            expected_prefix = (
                hashlib.sha256("Arun".encode("utf-8")).hexdigest()[:6]
            )
            self.assertEqual(output, f"{expected_prefix} 25 Leopard")
        finally:
            sys.stdout = saved_stdout


if __name__ == "__main__":
    unittest.main()
