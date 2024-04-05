"""Most of this code is modified from https://github.com/asottile/reorder-python-imports/blob/main/reorder_python_imports.py
which is available under the MIT License below:

Copyright (c) 2014 Anthony Sottile

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import enum
import re
from collections.abc import Generator


class TokenType(enum.Enum):
    IMPORT = 0
    STRING = 1
    NEWLINE = 2


COMMENT = r"#[^\r\n]*"
NAME = r"\w+"
PREFIX = r"[RrUu]?"
SINGLE_1 = r"'[^'\\]*(?:\\.[^'\\]*)*'"
DOUBLE_1 = r'"[^"\\]*(?:\\.[^"\\]*)*"'
SINGLE_3 = r"'''[^'\\]*(?:(?:\\.|\\\n|'(?!''))[^'\\]*)*'''"
DOUBLE_3 = r'"""[^"\\]*(?:(?:\\.|\\\n|"(?!""))[^"\\]*)*"""'

WS = r"[ \f\t]+"
IMPORT = rf"(?:from|import)(?={WS})"
EMPTY = rf"[ \f\t]*(?=\n|{COMMENT})"
OP = "[,.*]"
ESCAPED_NL = r"\\\n"
NAMES = rf"\((?:\s+|,|{NAME}|{ESCAPED_NL}|{COMMENT})*\)"
STRING = rf"{PREFIX}(?:{DOUBLE_3}|{SINGLE_3}|{DOUBLE_1}|{SINGLE_1})"


def group(base: str, pats: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(rf'{base}' rf'(?:{"|".join(pats)})*' rf'({COMMENT})?' rf'(?:\n|$)')


TOKENIZE: tuple[tuple[TokenType, re.Pattern[str]], ...] = (
    (TokenType.IMPORT, group(IMPORT, (WS, NAME, OP, ESCAPED_NL, NAMES))),
    (TokenType.NEWLINE, group(EMPTY, ())),
    (TokenType.STRING, group(STRING, (WS, STRING, ESCAPED_NL))),
)


def tokenize_pre_code(src: str) -> Generator[tuple[TokenType, str], None, None]:
    pos = 0
    while True:
        for tp, reg in TOKENIZE:
            if match := reg.match(src, pos):
                yield (tp, match[0])
                pos = match.end()
                break
        else:
            return


def get_imported_experimental_flags(src: str) -> set[str]:
    potential_flags: set[str] = set()
    for tok_type, line in tokenize_pre_code(src):
        if tok_type is TokenType.IMPORT and line.startswith("from __experimental__ import "):
            potential_line = line.removeprefix("from __experimental__ import ")
            for match in re.finditer(NAME, potential_line):
                if match[0] == "as":
                    continue
                potential_flags.add(match[0])
    return potential_flags
