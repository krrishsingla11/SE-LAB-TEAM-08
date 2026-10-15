from collections import Counter


def evaluate(target, guess):
    result = ["gray"] * len(guess)
    remaining = Counter(target)

    # Pass 1: exact matches (green) consume letters from the target's counts
    for i, ch in enumerate(guess):
        if ch == target[i]:
            result[i] = "green"
            remaining[ch] -= 1

    # Pass 2: yellow only if that letter still has a remaining count
    for i, ch in enumerate(guess):
        if result[i] == "green":
            continue
        if remaining[ch] > 0:
            result[i] = "yellow"
            remaining[ch] -= 1

    return result