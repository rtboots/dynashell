import sys
from simpleshell.classes import Shell

def instance():

    return Shell.Instance

if __name__ == "__main__":

    Shell(' '.join(sys.argv))