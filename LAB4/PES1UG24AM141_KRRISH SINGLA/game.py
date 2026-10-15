import random
from words import WORDS
from feedback import evaluate

MAX_GUESSES = 6


class WordleGame:
    def __init__(self, length=5):
        self.length = length
        self.target = random.choice([w for w in WORDS if len(w) == length])
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
            if guess not in WORDS:
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