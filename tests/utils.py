from contextlib import contextmanager

# Used in tests to wrap a function and verify
# it was calld with specific arguments or not
class CallTracker:
    def __init__(self):
        self.calls = []

    def track(self, obj, method_name):
        method = getattr(obj, method_name)
        def wrapper(obj, *args, **kwargs):
            self.calls.append((method_name, args, kwargs))
            return method(obj, *args, **kwargs)

        setattr(obj, method_name, wrapper)

    def was_called_with(self, method_name, *args, **kwargs):
        return any(call[0] == method_name and call[1] == args for call in self.calls)

@contextmanager
def track_calls(obj, method_name):
    tracker = CallTracker()
    tracker.track(obj, method_name)
    yield tracker

