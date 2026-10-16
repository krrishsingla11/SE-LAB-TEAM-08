from game import WordleGame

VALID_LENGTHS = ("4", "5", "6")


def choose_length():
    """Ask until the player picks 4, 5 or 6. Returns an int, or None for quit."""
    while True:
        choice = input("Choose word length (4, 5 or 6): ").strip().lower()
        if choice == "quit":
            return None
        if choice in VALID_LENGTHS:
            return int(choice)
        print("Please enter 4, 5 or 6.")


def main():
    while True:
        length = choose_length()
        if length is None:
            print("Thanks for playing!")
            return
        try:
            game = WordleGame(length)
        except ValueError as error:
            print(error)
            continue
        game.run()
        return


if __name__ == "__main__":
    main()