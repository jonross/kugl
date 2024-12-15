

def fail(message: str):
    raise KugelError(message)


class KugelError(Exception):
    pass
