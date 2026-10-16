def evaluate(target, guess):
    result = ["gray"] * len(guess)

    # Pass 1: greens
    for i in range(len(guess)):
        if guess[i] == target[i]:
            result[i] = "green"

    # Count target letters not used up by greens
    remaining = {}
    for i in range(len(target)):
        if result[i] != "green":
            remaining[target[i]] = remaining.get(target[i], 0) + 1

    # Pass 2: yellows, using up one copy each time
    for i in range(len(guess)):
        if result[i] == "green":
            continue
        if remaining.get(guess[i], 0) > 0:
            result[i] = "yellow"
            remaining[guess[i]] -= 1

    return result