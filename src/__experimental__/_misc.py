# region License
# The code up to but not including get_imported_experimental_flags() is mostly
# modified from https://github.com/asottile/reorder-python-imports/blob/main/reorder_python_imports.py
# which is available under the MIT License below:
#
# Copyright (c) 2014 Anthony Sottile
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# endregion

import enum
import keyword
import re
from collections.abc import Callable, Generator
from typing import ParamSpec, TypeVar


_T = TypeVar("_T")
_P = ParamSpec("_P")

__all__ = ("copy_annotations", "get_imported_experimental_flags")


class TokenType(enum.Enum):
    IMPORT = 0
    STRING = 1
    NEWLINE = 2


COMMENT = r"#[^\r\n]*"
NAME = r"\w+"
PREFIX = r"[RrUu]?"
DOUBLE_3 = r'"""[^"\\]*(?:(?:\\.|\\\n|"(?!""))[^"\\]*)*"""'
SINGLE_3 = r"'''[^'\\]*(?:(?:\\.|\\\n|'(?!''))[^'\\]*)*'''"
DOUBLE_1 = r'"[^"\\]*(?:\\.[^"\\]*)*"'
SINGLE_1 = r"'[^'\\]*(?:\\.[^'\\]*)*'"

WS = r"[ \f\t]+"
IMPORT = rf"(?:from|import)(?={WS})"
EMPTY = rf"[ \f\t]*(?=\n|{COMMENT})"
OP = "[,.*]"
ESCAPED_NL = r"\\\n"
NAMES = rf"\((?:\s+|,|{NAME}|{ESCAPED_NL}|{COMMENT})*\)"
STRING = rf"{PREFIX}(?:{DOUBLE_3}|{SINGLE_3}|{DOUBLE_1}|{SINGLE_1})"


def _create_pattern(base: str, pats: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(rf'{base}(?:{"|".join(pats)})*({COMMENT})?(?:\n|$)')


TOKENIZE: tuple[tuple[TokenType, re.Pattern[str]], ...] = (
    (TokenType.IMPORT, _create_pattern(IMPORT, (WS, NAME, OP, ESCAPED_NL, NAMES))),
    (TokenType.NEWLINE, _create_pattern(EMPTY, ())),
    (TokenType.STRING, _create_pattern(STRING, (WS, STRING, ESCAPED_NL))),
)

_FROM_EXPERIMENTAL = "from __experimental__ import "


def _tokenize_pre_code(source: str) -> Generator[tuple[TokenType, str]]:
    pos = 0
    while True:
        for tp, reg in TOKENIZE:
            if match := reg.match(source, pos):
                yield (tp, match[0])
                pos = match.end()
                break
        else:
            return


def get_imported_experimental_flags(source: str) -> set[str]:
    """Find all the imports from __experimental__ that were made at the top of a Python file."""

    # Attempts were made to switch over to a tokenize-based version, but it was 10x slower.
    potential_flags: set[str] = set()
    for tok_type, line in _tokenize_pre_code(source):
        if tok_type is TokenType.IMPORT and line.startswith(_FROM_EXPERIMENTAL):
            potential_line = re.sub(COMMENT, "", line.removeprefix(_FROM_EXPERIMENTAL))
            for name in re.finditer(NAME, potential_line):
                if keyword.iskeyword(name[0]):
                    continue
                potential_flags.add(name[0])
    return potential_flags


def copy_annotations(original_func: Callable[_P, _T]) -> Callable[[Callable[..., object]], Callable[_P, _T]]:
    """A decorator that copies the annotations from one function onto another.

    It may be a lie, but the lie can aid type checkers, IDEs, intellisense, etc.
    """

    def inner(new_func: Callable[..., object]) -> Callable[_P, _T]:
        # functools.wraps is overkill for this.
        try:
            new_func.__annotations__ = original_func.__annotations__
        except AttributeError:
            pass
        return new_func  # type: ignore # A lie.

    return inner
