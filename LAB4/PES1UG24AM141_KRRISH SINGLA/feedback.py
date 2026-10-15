def evaluate(target, guess):

    # occurrence, producing incorrect duplicate-letter feedback.
    result = ["gray"] * len(guess)
    for i, ch in enumerate(guess):
        if ch == target[i]:
            result[i] = "green"
    for i, ch in enumerate(guess):
        if result[i] == "green":
            continue
        if ch in target:
            result[i] = "yellow"
    return result
