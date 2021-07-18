import flask
import functools


def logged(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not flask.session.get("user"):
            return "Unauthorized", 401
        return f(*args, **kwargs)

    return wrapper


def ranked(rank):
    def inner(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if not flask.session.get("user"):
                return "Unauthorized", 401
            if flask.session.get("rank", 0) < rank:
                return "Forbidden", 403
            return f(*args, **kwargs)

        return wrapper

    return inner
