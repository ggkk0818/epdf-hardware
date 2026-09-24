"""Minimal s-expression reader/writer for KiCad files."""


def tokenize(text):
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "(" or c == ")":
            yield c
            i += 1
            continue
        if c == '"':
            i += 1
            buf = []
            while i < n:
                ch = text[i]
                if ch == "\\":
                    buf.append(text[i + 1])
                    i += 2
                    continue
                if ch == '"':
                    i += 1
                    break
                buf.append(ch)
                i += 1
            yield ("str", "".join(buf))
            continue
        j = i
        while j < n and text[j] not in ' \t\r\n()"':
            j += 1
        yield ("atom", text[i:j])
        i = j


def parse(text):
    stack = []
    root = None
    for tok in tokenize(text):
        if tok == "(":
            new = []
            if stack:
                stack[-1].append(new)
            elif root is None:
                root = new
            stack.append(new)
        elif tok == ")":
            stack.pop()
        else:
            kind, val = tok
            node = val
            if stack:
                stack[-1].append(node)
            else:
                root = node
    return root


def is_list(node):
    return isinstance(node, list)


def head(node):
    if is_list(node) and node and isinstance(node[0], str):
        return node[0]
    return None


def children(node, name):
    return [c for c in node if is_list(c) and head(c) == name]


def child(node, name):
    for c in node:
        if is_list(c) and head(c) == name:
            return c
    return None


def atoms(node):
    return [c for c in node if isinstance(c, str)]


def lists(node):
    return [c for c in node if is_list(c)]
