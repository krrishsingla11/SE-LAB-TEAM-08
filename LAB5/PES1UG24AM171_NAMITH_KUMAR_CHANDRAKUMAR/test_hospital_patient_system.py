"""Unit tests for hospital_patient_system module."""

import unittest
from hospital_patient_system import (
    PATIENT_RECORDS,
    admit_patient,
    discharge_patient,
    verify_admission_status,
    calculate_treatment_cost,
    generate_patient_hash,
    generate_ward_token,
    get_ward_summary,
)


class TestHospitalPatientSystem(unittest.TestCase):
    """Test suite covering core functionalities and edge cases."""

    def test_admit_patient(self):
        """Test admitting new and existing patients."""
        log = []
        result = admit_patient("P999", "Test Patient", "General", log)
        self.assertTrue(result)
        self.assertIn("P999", PATIENT_RECORDS)
        self.assertTrue(PATIENT_RECORDS["P999"]["is_admitted"])
        self.assertEqual(len(log), 1)

        # Duplicate admission should fail
        duplicate_result = admit_patient("P999", "Duplicate", "ICU")
        self.assertFalse(duplicate_result)

    def test_discharge_patient(self):
        """Test discharging valid and non-existent patients."""
        discharge_patient("P101")
        self.assertFalse(PATIENT_RECORDS["P101"]["is_admitted"])

        # Discharging non-existent patient should not raise KeyError
        try:
            discharge_patient("NON_EXISTENT")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.fail(f"discharge_patient raised unexpected exception {exc}")

    def test_verify_admission_status(self):
        """Test status checks for admitted, discharged, and missing patients."""
        self.assertTrue(verify_admission_status("P103"))
        self.assertFalse(verify_admission_status("P102"))
        self.assertFalse(verify_admission_status("UNKNOWN_ID"))

    def test_calculate_treatment_cost(self):
        """Test treatment cost calculation with multipliers."""
        cost = calculate_treatment_cost("P103", 1.12)
        self.assertAlmostEqual(cost, 1200.0 * 1.12, places=2)

    def test_generate_patient_hash(self):
        """Test that SHA-256 hash is generated and is 64 hex characters."""
        patient_hash = generate_patient_hash("P103")
        self.assertEqual(len(patient_hash), 64)
        self.assertEqual(
            patient_hash,
            generate_patient_hash("P103"),
        )

    def test_generate_ward_token(self):
        """Test that ward token is a 4-digit number between 1000 and 9999."""
        for _ in range(50):
            token = generate_ward_token()
            self.assertGreaterEqual(token, 1000)
            self.assertLessEqual(token, 9999)

    def test_get_ward_summary(self):
        """Test active count summation."""
        active = get_ward_summary(PATIENT_RECORDS)
        self.assertIsInstance(active, int)
        self.assertGreaterEqual(active, 0)


if __name__ == "__main__":
    unittest.main()
