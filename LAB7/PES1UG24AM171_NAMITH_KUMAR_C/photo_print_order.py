import math


def parse_order(text):
    """Parse 'size:copies' string into (UPPERCASE_SIZE, positive_copies).

    Raises:
        TypeError: If text is not a string.
        ValueError: If format is invalid, size is empty, or copies is not a positive integer.
    """
    if not isinstance(text, str):
        raise TypeError("Order text must be a string.")

    parts = text.split(":")
    if len(parts) != 2:
        raise ValueError("Order text must be in 'size:copies' format.")

    size = parts[0].strip()
    copies_str = parts[1].strip()

    if not size:
        raise ValueError("Print size must not be empty.")

    if not (copies_str.isascii() and copies_str.isdigit()):
        raise ValueError("Copies must be a positive integer.")

    copies = int(copies_str)
    if copies <= 0:
        raise ValueError("Copies must be a positive integer.")

    return size.upper(), copies


def file_size_average(sizes_csv):
    """Parse comma-separated non-negative integer file sizes and return floor average.

    Raises:
        TypeError: If sizes_csv is not a string.
        ValueError: If sizes_csv is empty, contains non-integer tokens, or negative sizes.
    """
    if not isinstance(sizes_csv, str):
        raise TypeError("File sizes input must be a string.")

    stripped = sizes_csv.strip()
    if not stripped:
        raise ValueError("At least one file size is required.")

    tokens = [t.strip() for t in sizes_csv.split(",")]
    if not tokens or any(t == "" for t in tokens):
        raise ValueError("File sizes cannot have empty comma-separated tokens.")

    values = []
    for t in tokens:
        if not (t.isascii() and (t.isdigit() or (t.startswith("-") and t[1:].isdigit()))):
            raise ValueError("All file sizes must be valid integers.")
        val = int(t)
        if val < 0:
            raise ValueError("File sizes must be non-negative integers.")
        values.append(val)

    if not values:
        raise ValueError("At least one file size is required.")

    return sum(values) // len(values)


def payable_amount(text):
    """Parse 'amount|discount' string and return payable amount with 18% GST (min 0).

    Formula: max(amount * 1.18 - discount, 0.0), rounded to 2 decimal places.

    Raises:
        TypeError: If text is not a string.
        ValueError: If format is invalid, non-numeric, non-finite, or negative.
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string.")

    parts = text.split("|")
    if len(parts) != 2:
        raise ValueError("Input must be in 'amount|discount' format.")

    amount_str = parts[0].strip()
    discount_str = parts[1].strip()

    try:
        amount = float(amount_str)
        discount = float(discount_str)
    except ValueError as exc:
        raise ValueError("Amount and discount must be valid numbers.") from exc

    if not (math.isfinite(amount) and math.isfinite(discount)):
        raise ValueError("Amount and discount must be finite numbers.")

    if amount < 0 or discount < 0:
        raise ValueError("Amount and discount must be non-negative.")

    total = amount * 1.18 - discount
    if not math.isfinite(total):
        raise ValueError("Calculated payable amount is out of supported range.")

    return round(max(total, 0.0), 2)


def main():
    print("==== Running parse_order ====")
    user_input = input("Enter print size:copies (e.g. 4x6:25): ")
    result = parse_order(user_input)
    print("Size and Copies:", result)

    print("\n==== Running file_size_average ====")
    user_input = input("Enter file sizes in MB as CSV (e.g. 4,8,12): ")
    result = file_size_average(user_input)
    print("Average File Size:", result)

    print("\n==== Running payable_amount ====")
    user_input = input("Enter amount|discount (e.g. 450|50): ")
    result = payable_amount(user_input)
    print("Payable Amount:", result)


if __name__ == "__main__":
    main()
