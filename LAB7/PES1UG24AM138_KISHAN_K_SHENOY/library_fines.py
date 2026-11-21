"""Library Fines module for member parsing, fine computation, and shelf indexing.

Defensively hardened for Lab 7 fuzz testing and property-based verification.
"""


def parse_member_id(member_id):
    """Parse 'type-number' string into (UPPERCASE_TYPE, integer_number).

    Args:
        member_id (str): Member identifier such as 'STU-1023'.

    Returns:
        tuple[str, int]: Parsed member type in uppercase and member number.

    Raises:
        TypeError: If member_id is not a string.
        ValueError: If delimiter format is invalid, type is empty, or number is invalid.
    """
    if not isinstance(member_id, str):
        raise TypeError("Member ID must be a string.")

    parts = member_id.split("-")
    if len(parts) != 2:
        raise ValueError("Member ID must be in 'type-number' format.")

    member_type = parts[0].strip()
    number_str = parts[1].strip()

    if not member_type:
        raise ValueError("Member type must not be empty.")

    if not (number_str.isascii() and (number_str.isdigit() or (number_str.startswith("-") and number_str[1:].isdigit()))):
        raise ValueError("Member number must be an integer.")

    number = int(number_str)
    if number < 0:
        raise ValueError("Member number must be non-negative.")

    return member_type.upper(), number


def total_fine(days_csv):
    """Calculate total overdue fine from a comma-separated list of days kept.

    Each day beyond 14 days incurs a fine of 2 units.

    Args:
        days_csv (str): Comma-separated integer days such as '10,20,30'.

    Returns:
        int: Total accumulated overdue fine.

    Raises:
        TypeError: If days_csv is not a string.
        ValueError: If input is empty, tokens are malformed, or days are negative.
    """
    if not isinstance(days_csv, str):
        raise TypeError("Days kept input must be a string.")

    stripped = days_csv.strip()
    if not stripped:
        raise ValueError("At least one entry of days kept is required.")

    tokens = [t.strip() for t in days_csv.split(",")]
    if not tokens or any(t == "" for t in tokens):
        raise ValueError("Days CSV cannot contain empty tokens.")

    fine = 0
    for t in tokens:
        if not (t.isascii() and (t.isdigit() or (t.startswith("-") and t[1:].isdigit()))):
            raise ValueError("All days kept entries must be valid integers.")
        d = int(t)
        if d < 0:
            raise ValueError("Days kept cannot be negative.")
        if d > 14:
            fine += (d - 14) * 2

    return fine


def shelf_code(title):
    """Generate two-letter uppercase shelf code from the first two words of a title.

    Args:
        title (str): Book title containing at least two words.

    Returns:
        str: Two-letter uppercase shelf code.

    Raises:
        TypeError: If title is not a string.
        ValueError: If title contains fewer than two words.
    """
    if not isinstance(title, str):
        raise TypeError("Title must be a string.")

    words = title.strip().split()
    if len(words) < 2:
        raise ValueError("Title must contain at least two words.")

    first_char = words[0][0]
    second_char = words[1][0]
    return (first_char + second_char).upper()


def main():
    """Interactive demonstration for library fines utilities."""
    print("==== Running parse_member_id ====")
    user_input = input("Enter a member ID (e.g. STU-1023): ")
    try:
        result = parse_member_id(user_input)
        print("Member Type and Number:", result)
    except (ValueError, TypeError) as err:
        print("Error:", err)

    print("\n==== Running total_fine ====")
    user_input = input("Enter days kept for each book as CSV (e.g. 10,20,30): ")
    try:
        result = total_fine(user_input)
        print("Total Fine:", result)
    except (ValueError, TypeError) as err:
        print("Error:", err)

    print("\n==== Running shelf_code ====")
    user_input = input("Enter a book title with at least two words: ")
    try:
        result = shelf_code(user_input)
        print("Shelf Code:", result)
    except (ValueError, TypeError) as err:
        print("Error:", err)


if __name__ == "__main__":
    main()
