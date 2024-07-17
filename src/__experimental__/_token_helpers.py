import tokenize


__all__ = ("offset_token_horizontal", "offset_line_horizontal")


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
