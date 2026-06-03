"""
Minimal serializer for MicroPython using repr/eval.

This works well for simple Python objects (dicts, lists, ints, strings).
It is safe for our use case because we only receive data from paired,
trusted ESP32 devices — do not use this on untrusted input.
"""


def dumps(obj):
    """Serialize obj to bytes using Python's repr()."""
    return repr(obj).encode()


def loads(data):
    """Deserialize bytes back to a Python object."""
    text = data.decode()
    context = {}
    # If the repr contains a qualified name (e.g. a class instance), import
    # the module so eval can resolve it.
    if "(" in text:
        qualname = text.split("(", 1)[0]
        if "." in qualname:
            pkg = qualname.rsplit(".", 1)[0]
            mod = __import__(pkg)
            context[pkg] = mod
    return eval(text, context)
