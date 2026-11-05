"""arizdot — a small dot for keeping an eye on your work."""
from pulse import main

if __name__ == "__main__":
    from autostart import singleton
    if singleton('arizdot.ui'):main()
