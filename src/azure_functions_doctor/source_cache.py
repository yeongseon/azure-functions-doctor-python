"""Bounded AST reuse scoped to one diagnostic phase, never shared across scans."""

import ast
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_trees: ContextVar[dict[str, ast.Module] | None] = ContextVar("source_trees", default=None)
_MAX_TREES = 128


@contextmanager
def source_cache() -> Iterator[None]:
    token = _trees.set({})
    try:
        yield
    finally:
        _trees.reset(token)


def parse_source(source: str) -> ast.Module:
    trees = _trees.get()
    if trees is None:
        return ast.parse(source)
    if source in trees:
        return trees[source]
    tree = ast.parse(source)
    if len(trees) < _MAX_TREES:
        trees[source] = tree
    return tree
