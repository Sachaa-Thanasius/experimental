# The code up to and including get_imported_experimental_flags() is mostly
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

import enum
import re
import tokenize
from typing import Generator, Iterable, Pattern, Set, Tuple

__all__ = ("get_imported_experimental_flags",)


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


def _create_pattern(base: str, pats: Tuple[str, ...]) -> Pattern[str]:
    return re.compile(rf'{base}(?:{"|".join(pats)})*({COMMENT})?(?:\n|$)')


TOKENIZE: Tuple[Tuple[TokenType, Pattern[str]], ...] = (
    (TokenType.IMPORT, _create_pattern(IMPORT, (WS, NAME, OP, ESCAPED_NL, NAMES))),
    (TokenType.NEWLINE, _create_pattern(EMPTY, ())),
    (TokenType.STRING, _create_pattern(STRING, (WS, STRING, ESCAPED_NL))),
)

_FROM_EXPERIMENTAL = "from __experimental__ import "


def _tokenize_pre_code(source: str) -> Generator[Tuple[TokenType, str], None, None]:
    pos = 0
    while True:
        for tp, reg in TOKENIZE:
            if match := reg.match(source, pos):
                yield (tp, match[0])
                pos = match.end()
                break
        else:
            return


def get_imported_experimental_flags(source: str) -> Set[str]:
    """Find all the imports from __experimental__ that were made at the top of a Python file."""

    # Attempts were made to switch over to a tokenize-based version, but it was 10x slower.
    potential_flags: set[str] = set()
    for tok_type, line in _tokenize_pre_code(source):
        if tok_type is TokenType.IMPORT and line.startswith(_FROM_EXPERIMENTAL):
            potential_line = re.sub(COMMENT, "", line[len(_FROM_EXPERIMENTAL) :])
            for name in re.finditer(NAME, potential_line):
                if name[0] == "as":
                    continue
                potential_flags.add(name[0])
    return potential_flags


def offset_token_horizontal(tok: tokenize.TokenInfo, offset: int) -> tokenize.TokenInfo:
    start_row, start_col = tok.start
    end_row, end_col = tok.end
    return tok._replace(start=(start_row, start_col + offset), end=(end_row, end_col + offset))


def offset_line_horizontal(
    tokens: Iterable[tokenize.TokenInfo],
    line: int,
    offset: int,
) -> Generator[tokenize.TokenInfo, None, None]:
    for tok in tokens:
        if line != tok.start[0]:
            yield tok
            break

        yield offset_token_horizontal(tok, offset)
