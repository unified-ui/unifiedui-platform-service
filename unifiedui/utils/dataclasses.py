from dataclasses import asdict
from typing import TypeVar

T = TypeVar("T")


def to_dict[T](cls: type[T]) -> type[T]:
    """
    Decorator that adds a to_dict() method to a dataclass.
    The method returns a dictionary representation using dataclasses.asdict().

    Usage:
        @with_to_dict
        @dataclass
        class MyClass:
            field1: str
            field2: int
    """

    def to_dict(self) -> dict:
        return asdict(self)

    cls.to_dict = to_dict
    return cls
