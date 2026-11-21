DAILY_FINE = {"student": 2, "faculty": 1, "guest": 5}


def late_fine(member, days_kept, is_damaged):
    if member not in DAILY_FINE:
        raise ValueError("unknown member")
    if days_kept < 0:
        raise ValueError("invalid days")
    if member == "faculty":
        loan_days = 30
    else:
        loan_days = 14
    overdue = days_kept - loan_days
    fine = 0
    if overdue > 0:
        fine = overdue * DAILY_FINE[member]
        if fine > 200:
            fine = 200
    if is_damaged:
        fine += 150
    return fine


def can_borrow(books_held, pending_fine, member):
    if pending_fine > 100:
        return False
    if member == "faculty":
        return books_held < 10
    return books_held < 3


def renewal_status(times_renewed, has_reservation, days_left):
    if has_reservation:
        return "denied"
    if times_renewed >= 2:
        return "limit reached"
    elif days_left < 0:
        return "overdue"
    return "renewed"
