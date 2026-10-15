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

    def run(self):
        print(f"Wordle — {self.length} letters, {MAX_GUESSES} guesses. Type q to quit.")
        while len(self.history) < MAX_GUESSES:
            guess = input("> ").strip().lower()
            if guess == "q":
                return
            if len(guess) != self.length or not guess.isalpha():
                print(f"Enter a {self.length}-letter word.")
                continue
            if guess not in self.words:
                print("Not in word list.")
                continue
            feedback = evaluate(self.target, guess)
            self.history.append((guess, feedback))
            print(" ".join(feedback))
            if guess == self.target:
                tries = len(self.history)
                print(f"You win! Solved in {tries} guess{'es' if tries != 1 else ''}.")
                return
            print(f"{MAX_GUESSES - len(self.history)} guesses left.")
        print(f"You lose. The word was: {self.target}")