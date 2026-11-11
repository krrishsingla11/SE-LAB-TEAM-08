FIXED_CHARGE = {"domestic": 50, "commercial": 150}


def energy_charge(units, connection):
    if connection not in FIXED_CHARGE:
        raise ValueError("unknown connection")
    if units < 0:
        raise ValueError("invalid units")
    if units <= 100:
        charge = units * 3
    elif units <= 300:
        charge = 300 + (units - 100) * 5
    else:
        charge = 1300 + (units - 300) * 8
    if connection == "commercial":
        charge = charge * 2
    return charge + FIXED_CHARGE[connection]


def late_fee(bill_amount, days_late):
    if days_late <= 0:
        return 0
    if days_late <= 15:
        fee = 50
    else:
        fee = 100
        if bill_amount > 2000:
            fee += bill_amount // 20
    return fee


def subsidy(units, is_senior, has_solar):
    amount = 0
    if units <= 100 and is_senior:
        amount = 50
    if has_solar:
        amount += 100
        if units > 300:
            amount = 0
    return amount
