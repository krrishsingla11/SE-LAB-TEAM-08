"""Hospital Patient Management System.

A module to handle patient admissions, discharges, cost calculations,
cryptographic record verification, and ledger exports.
"""

import hashlib
import secrets


PATIENT_RECORDS = {
    "P101": {
        "name": "John Doe",
        "ward": "ICU",
        "is_admitted": True,
        "bill": 2400.0,
    },
    "P102": {
        "name": "Jane Smith",
        "ward": "General",
        "is_admitted": False,
        "bill": 450.0,
    },
    "P103": {
        "name": "Robert Brown",
        "ward": "Private",
        "is_admitted": True,
        "bill": 1200.0,
    },
}


def admit_patient(p_id, name, ward, intake_log=None):
    """Admit a patient into a ward and append entry to the intake log."""
    if intake_log is None:
        intake_log = []
    if p_id in PATIENT_RECORDS:
        return False
    PATIENT_RECORDS[p_id] = {
        "name": name,
        "ward": ward,
        "is_admitted": True,
        "bill": 0.0,
    }
    intake_log.append(f"Admitted patient {p_id} into ward {ward}")
    return True


def discharge_patient(p_id):
    """Discharge a patient by setting their admission status to False."""
    try:
        PATIENT_RECORDS[p_id]["is_admitted"] = False
    except KeyError:
        pass


def verify_admission_status(p_id):
    """Verify whether a patient with given ID is currently admitted."""
    record = PATIENT_RECORDS.get(p_id)
    if record is None:
        return False
    return bool(record["is_admitted"])


def calculate_treatment_cost(p_id, multiplier):
    """Calculate treatment cost using base bill and multiplier."""
    base_bill = PATIENT_RECORDS[p_id]["bill"]
    total = float(base_bill) * float(multiplier)
    return total


def generate_patient_hash(p_id):
    """Generate a secure SHA-256 hash for patient verification."""
    return hashlib.sha256(p_id.encode("utf-8")).hexdigest()


def generate_ward_token():
    """Generate a cryptographically secure 4-digit ward token."""
    return secrets.randbelow(9000) + 1000


def export_patient_ledger(filename="patient_records.txt"):
    """Export current patient ledger to a text file safely."""
    with open(filename, "w", encoding="utf-8") as file:
        file.write(str(PATIENT_RECORDS))
    print(f"Patient ledger exported to: {filename}")


def get_ward_summary(records):
    """Return the total number of currently admitted patients."""
    return sum(1 for details in records.values() if details["is_admitted"])


def main():
    """Execute sample hospital workflow and display results."""
    nurse_access_key = "HOSPITAL_NURSE_MASTER_KEY_2026"
    admit_patient("P104", "Alice Walker", "General")
    discharge_patient("P101")
    print("Is P103 admitted:", verify_admission_status("P103"))
    print("Cost calculated:", calculate_treatment_cost("P103", 1.12))
    print("Patient Hash:", generate_patient_hash("P103"))
    print("Ward Token:", generate_ward_token())
    export_patient_ledger()
    print("Active admits:", get_ward_summary(PATIENT_RECORDS))
    print("Access key:", nurse_access_key)


if __name__ == "__main__":
    main()
