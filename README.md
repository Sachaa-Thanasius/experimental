# experimental
Yet another way of messing with non-existent features in Python.

This is a personal `__future__`-like collection of features that will only be active if imported from `__experimental__` near the top of a Python file. Some of those features include:

- Late-bound function argument defaults
    - Based on [PEP 671](https://peps.python.org/pep-0671/).
    - Currently, the late-bound expressions must be surrounded in parentheses, unlike the syntax proposed in the relevant PEP.
- Module-level and context manager-level lazy imports
    - Based on [PEP 690](https://peps.python.org/pep-0690/) and several other attempts at lazy importing.
    - Currently, `from` imports are evaluated eagerly.
- Inline import expressions
    - Based on [import-expression](https://github.com/ioistired/import-expression-parser).
- Elision of `typing.cast`/`typing_extensions.cast`
    - Based on past discussions had about possibly eliminating the cost of `cast`.

They shouldn't be mutually exclusive syntax-wise.


## Installation
```shell
python -m pip install https://github.com/Sachaa-Thanasius/experimental
```
I don't see a reason to put this on PyPI as of now.


## Examples
```py
"""example1.py"""
from __experimental__ import late_bound_arg_defaults

def bisect_right(a, x, lo=0, hi=>(len(a)), *, key=None):
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

# All module imports within this file henceforth should be performed lazily,
# i.e. delaying module load until accessing an attribute from the module.
...
```


## Caveats
### Registration
This package uses a `.pth` file to register an import hook on interpreter startup. The hook replaces the built-in file finder's [`path hook`](https://docs.python.org/3/library/importlib.html#importlib.machinery.FileFinder.path_hook) on [`sys.path_hooks`](https://docs.python.org/3/library/sys.html#sys.path_hooks). That should work fine if you're using a regular setup with site packages, where that `.pth` file should end up.

However, if your environment is atypical, you might need to manually register that finder to have your code be processed by this package. Do so in a file away from the rest of your code, before any of it executes. For example:

```py
import __experimental__
__experimental__.install()
import your_actual_module
```


## Documentation
See the docstrings and comments in the code. They're currently a little bare, but they will improve over time.


## Why?
It's fun. It's also a learning experience in manipulating Python via import hooks, AST transformations, token stream transformations, and more.


## Acknowledgements
- aroberge's [ideas](https://github.com/aroberge/ideas) package, which introduced me to the idea of modifying Python like this.
- asottile's future packages, including things like [future-fstrings](https://github.com/asottile-archive/future-fstrings), that are practical applications showcasing the usefulness of these kinds of transformations ("memes" though they may be).
- RocketRace's [hoopy](https://github.com/RocketRace/hoopy) and [custom-literals](https://github.com/RocketRace/custom-literals) packages, which are much more interesting, complex, and featured Python manipulations.
- Those who wrote the original PEPs and packages that this attempts to (re)implement (see the links in the overview).
- Addendum: aroberge had the idea (and the code) for an `__experimental__` package well before I did, but I didn't know until well after making this.
