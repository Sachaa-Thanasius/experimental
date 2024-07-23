import tokenize
from collections.abc import Generator, Sequence
from typing import TypeVar


_T = TypeVar("_T")


__all__ = ("offset_token_horizontal", "offset_line_horizontal", "reverse_enumerate")


def offset_token_horizontal(tok: tokenize.TokenInfo, offset: int) -> tokenize.TokenInfo:
    """Take a token and return a new token with the columns for start and end offset by a given amount."""

    start_row, start_col = tok.start
    end_row, end_col = tok.end
    return tok._replace(start=(start_row, start_col + offset), end=(end_row, end_col + offset))


def offset_line_horizontal(
    tokens: list[tokenize.TokenInfo],
    offset: int,
    *,
    start_index: int = 0,
    line: int,
) -> None:
    """Modify a list of tokens by offsetting some of the tokens horizontally while they are on the given line.

    Parameters
    ----------
    tokens: list[tokenize.TokenInfo]
        The list of tokens to modify.
    offset: int
        The amount to offset the tokens horizontally by.
    start_index: int, default=0
        Where in the list to start modifying from. Defaults to 0, meaning the entire list.
    line: int
        Which line number to offset tokens on.

    Notes
    -----
    This modifies the list in place but does not change its length, so it should be safe to use during iteration.
    """

    for i, tok in enumerate(tokens[start_index:], start=start_index):
        if tok.start[0] != line:
            break
        tokens[i] = offset_token_horizontal(tok, offset)


def reverse_enumerate(sequence: Sequence[_T], start: int = -1) -> Generator[tuple[int, _T]]:
    """Yield index-value pairs from the given sequence, but in reverse. This generator defaults to starting at the end
    of the sequence unless the start index is given.

    Notes
    -----
    Sources of inspiration and code:
    https://stackoverflow.com/questions/529424/traverse-a-list-in-reverse-order-in-python
    https://github.com/asottile/tokenize-rt/blob/3edc03f25584af41f229b63280de557e1ec7d512/tokenize_rt.py#L116
    """

    if start == -1:
        start = len(sequence) - 1

    for i in range(start, -1, -1):
        yield i, sequence[i]
