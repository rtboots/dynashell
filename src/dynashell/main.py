import sys
from dynashell.classes import Shell

# Returns active shell instance
def instance():
    return Shell.Instance

# Script hook behind 'dynashell' module script
def run_shell():
    Shell(' '.join(sys.argv))

# Alternative shell execution via 'python -m dynashell.main ...'
if __name__ == "__main__":
    Shell(' '.join(sys.argv))