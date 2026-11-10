PLAN_PRICE = {"monthly": 1500, "quarterly": 4000, "yearly": 12000}


def membership_cost(plan, age, is_student, with_trainer):
    if plan not in PLAN_PRICE:
        raise ValueError("unknown plan")
    if age < 14:
        raise ValueError("too young")
    cost = PLAN_PRICE[plan]
    if age >= 60:
        cost -= cost // 4
    elif is_student:
        cost -= cost // 10
    if with_trainer:
        cost += 2000
        if plan == "yearly":
            cost -= 500
    return cost


def can_enter(hour, plan_active, is_women_only_slot, gender):
    if not plan_active:
        return False
    if hour < 5 or hour > 22:
        return False
    if is_women_only_slot:
        return gender == "F"
    return True


def bmi_category(weight_kg, height_m):
    if height_m <= 0:
        raise ValueError("invalid height")
    bmi = weight_kg / (height_m * height_m)
    if bmi < 18.5:
        return "underweight"
    elif bmi < 25:
        return "normal"
    elif bmi < 30:
        return "overweight"
    return "obese"
