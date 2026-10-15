import random
from words import WORDS
from feedback import evaluate

MAX_GUESSES = 6


def choose_length():
    lengths = sorted({len(w) for w in WORDS})
    options = ", ".join(str(n) for n in lengths)
    while True:
        choice = input(f"Choose word length ({options}): ").strip()
        if choice.isdigit() and int(choice) in lengths:
            return int(choice)
        print(f"Pick one of: {options}")


class WordleGame:
    def __init__(self, length=5):
        self.length = length
        self.words = [w for w in WORDS if len(w) == length]
        if not self.words:
            raise ValueError(f"No {length}-letter words available.")
        self.target = random.choice(self.words)
        self.history = []

    def show_history(self):
        for n, (guess, feedback) in enumerate(self.history, 1):
            cells = "  ".join(f"{c.upper()}:{f:<6}" for c, f in zip(guess, feedback))
            print(f"{n}. {cells}".rstrip())

    def show_summary(self, result):
        print("\n--- Summary ---")
        print(f"Target:  {self.target}")
        print(f"Result:  {result}")
        print(f"Guesses: {len(self.history)}/{MAX_GUESSES}")

    def run(self):
        print(f"Wordle — {self.length} letters, {MAX_GUESSES} guesses. Type q to quit.")
        result = "Loss"
        while len(self.history) < MAX_GUESSES:
            guess = input("> ").strip().lower()
            if guess == "q":
                result = "Quit"
                break
            if len(guess) != self.length or not guess.isalpha():
                print(f"Enter a {self.length}-letter word.")
                continue
            if guess not in self.words:
                print("Not in word list.")
                continue
            feedback = evaluate(self.target, guess)
            self.history.append((guess, feedback))
            self.show_history()
            if guess == self.target:
                tries = len(self.history)
                print(f"You win! Solved in {tries} guess{'es' if tries != 1 else ''}.")
                result = "Win"
                break
            print(f"{MAX_GUESSES - len(self.history)} guesses left.")
        else:
            print("You lose.")
        self.show_summary(result)