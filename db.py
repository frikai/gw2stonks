import json
from typing import List


class Jsonizable(object):
    def to_json(self) -> dict:
        raise NotImplementedError(f"Cannot serialize {self}, method 'to_json' is not defined")

    @classmethod
    def from_json(cls, *args, **kwargs):
        raise NotImplementedError(f"Cannot serialize {cls}, @classmethod 'from_json' is not defined")

