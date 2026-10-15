import random
from words import WORDS
from feedback import evaluate


class WordleGame:
    def __init__(self, length=5):
        self.length = length
        self.target = random.choice([w for w in WORDS if len(w) == length])
        self.history = []

    def run(self):
        print(f"Wordle — {self.length} letters, 6 guesses.")
        for _ in range(6):
            guess = input("> ").strip().lower()
            if guess == "q":
                return
            if len(guess) != self.length or not guess.isalpha():
                print("Enter a valid word of the required length.")
                continue
            feedback = evaluate(self.target, guess)
            self.history.append((guess, feedback))
            print(" ".join(feedback))
            if guess == self.target:
                print("Solved!")
                return
        print("The word was:", self.target)
