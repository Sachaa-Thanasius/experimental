# This code is copied from https://github.com/mikeshardmind/discord-rolebot/blob/main/rolebot/encoder.py
# which is available under the MPL License below:
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (C) 2023 Michael Hall <https://github.com/mikeshardmind>

from collections import deque
from collections.abc import Iterable
from typing import Generic, TypeVar

T = TypeVar("T")

__all__ = ("Peekable",)


class Peekable(Generic[T]):
    def __init__(self, iterable: Iterable[T]):
        self._it = iter(iterable)
        self._cache: deque[T] = deque()

    def __iter__(self):
        return self

    def has_more(self) -> bool:
        try:
            self.peek()
        except StopIteration:
            return False
        return True

    def peek(self) -> T:
        if not self._cache:
            self._cache.append(next(self._it))
        return self._cache[0]

    def __next__(self) -> T:
        if self._cache:
            return self._cache.popleft()
        return next(self._it)
