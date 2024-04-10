# experimental
Yet another way of messing with non-existent features in Python.

This is a personal `__future__`-like collection of features that will only be active if imported from `__experimental__` near the top of a Python file. Some of those features include:

- Late-bound function argument defaults
    - Based on [PEP 671](https://peps.python.org/pep-0671/)
- Module-level and context manager-level lazy imports
    - Based on [PEP 690](https://peps.python.org/pep-0690/) and a whole bunch of other attempts at lazy loading.
- Inline import expressions
    - Based on [import-expression](https://github.com/ioistired/import-expression-parser)

They should all work if imported together in a file.


## Installation
```shell
python -m pip install https://github.com/Sachaa-Thanasius/experimental
```
I don't see a reason to put this on PyPI as of now.


## Examples
```py
"""example1.py"""
from __experimental__ import late_bound_arg_defaults

def bisect_right(a, x, lo=0, hi=>len(a), *, key=None):
    # If nothing is passed in for hi, only then will it evaluate as len(a).
    # Late-bound defaults will be evaluated in left-to-right order.
    ...


"""example2.py"""
from __experimental__ import inline_import

# This will import the collections module and use it without having to place
# an import statement at the top of the file.
assert collections!.Counter("bccdddeeee") == {'e': 4, 'd': 3, 'c': 2, 'b': 1}


"""example3.py"""
from __experimental__ import lazy_import

# All module imports within this file henceforth should be performed lazily, i.e. delaying module load until accessing an attribute from the module.
...
```

## Documentation
See the docstrings and comments in the code. They're currently a little bare, but they will improve over time.


## Why
It's fun. It's also a learning experience in manipulating Python via import hooks, AST transformations, token stream transformations, and more.


## Acknowledgements
- aroberge's [ideas](https://github.com/aroberge/ideas), package which introduced me to the idea of modifying Python like this.
- asottile's future packages, including things like [future-fstrings](https://github.com/asottile-archive/future-fstrings), that are practical applications showcasing the usefulness of these kinds of transformations ("memes" though they may be).
- RocketRace's [hoopy](https://github.com/RocketRace/hoopy) and [custom-literals](https://github.com/RocketRace/custom-literals) packages, which are much more interesting, complex, and featured Python manipulations.
- Those who wrote the original PEPs and packages that this attempts to (re)implement (see the links in the overview).
