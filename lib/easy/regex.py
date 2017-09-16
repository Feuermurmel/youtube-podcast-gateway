import re


def grp(pattern, name=None):
    """
    Grouping. Defines a group with a given name and containing pattern.

    :param name:
        Name of the group which can be used to get the content of the group
        after matching. By default the group does not have a name.
    """
    if name is None:
        return '(?:%s)' % pattern
    else:
        return '(?P<%s>%s)' % (name, pattern)


def rep(pattern, repetition='*'):
    """
    Repetition. Match a pattern at least zero time.

    :param repetition:
        Pass a different repetition specifier like '+'.
    """
    return grp(pattern) + repetition


def opt(pattern):
    """
    Optional. Make a pattern optional.
    """
    return rep(pattern, '?')


def alt(*patterns):
    """
    Alternative. Build a pattern that matches one of multiple patterns.
    """
    return grp('|'.join(patterns))


def matchone(pattern, str):
    """
    Match a pattern against a string. The pattern must match the complete
    string. Returns a map from name to matched substring for all named groups
    in the pattern.
    """
    match = re.match(grp(pattern) + '$', str, re.DOTALL)

    if match is None:
        raise Exception('No match')

    return {k: v for k, v in match.groupdict().items() if v is not None}


def matchall(pattern, str):
    """
    Match a pattern multiple times. Returns an iterator of results from
    matchone().
    """
    patt = re.compile(pattern, re.DOTALL)
    pos = 0

    while pos < len(str):
        match = patt.match(str, pos)

        if match is None:
            lines = str[:pos].split('\n')
            line = len(lines)
            column = len(lines[-1])

            raise Exception('No match at: %s:%s: %s ...' % (line, column, str[pos:min(pos + 25, len(str))]))

        pos = match.end()

        yield {k: v for k, v in match.groupdict().items() if v is not None}
