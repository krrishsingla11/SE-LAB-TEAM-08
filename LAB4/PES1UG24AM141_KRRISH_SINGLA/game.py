import random
from words import WORDS
from feedback import evaluate

MAX_GUESSES = 6


def format_history(history):
    """Turn [(guess, feedback), ...] into numbered lines like '1. SPEED  gray yellow ...'."""
    return [
        f"{n}. {guess.upper()}  {' '.join(feedback)}"
        for n, (guess, feedback) in enumerate(history, start=1)
    ]


def print_history(history):
    print("--- Guesses so far ---")
    for line in format_history(history):
        print(line)


def print_summary(length, target, result, history):
    print()
    print("===== Game summary =====")
    print(f"Word length: {length}")
    print(f"Target word: {target.upper()}")
    print(f"Result: {result}")
    print(f"Accepted guesses: {len(history)}/{MAX_GUESSES}")
    print("History:")
    if history:
        for line in format_history(history):
            print(line)
    else:
        print("(no guesses)")


class WordleGame:
    def __init__(self, length=5):
        self.length = length
        self.words = [w for w in WORDS if len(w) == length]
        if not self.words:
            raise ValueError(f"No {length}-letter words in words.py. Add some to play this mode.")
        self.target = random.choice(self.words)
        self.history = []

    def validate(self, guess):
        """Return an error message, or None if the guess is OK."""
        if len(guess) != self.length:
            return f"Guess must be {self.length} letters long."
        if not guess.isalpha():
            return "Guess must contain letters only."
        if guess not in self.words:
            return "Not in the word list."
        return None

    def run(self):
        print(f"Wordle - {self.length} letters, {MAX_GUESSES} guesses. Type 'quit' to exit.")
        result = "lost"
        while len(self.history) < MAX_GUESSES:
            guess = input("> ").strip().lower()
            if guess == "quit":
                result = "quit"
                break
            error = self.validate(guess)
            if error:
                print(error)
                continue
            feedback = evaluate(self.target, guess)
            self.history.append((guess, feedback))
            print_history(self.history)
            if guess == self.target:
                result = "won"
                break

        if result == "won":
            print(f"You win! Solved in {len(self.history)}/{MAX_GUESSES} guesses.")
        elif result == "lost":
            print(f"You lose! The word was: {self.target}")
        else:
            print("Thanks for playing!")
        print_summary(self.length, self.target, result, self.history)