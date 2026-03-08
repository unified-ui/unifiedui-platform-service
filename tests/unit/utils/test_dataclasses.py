"""Unit tests for unifiedui/utils/dataclasses.py"""

from dataclasses import asdict as dataclasses_asdict
from dataclasses import dataclass

from unifiedui.utils.dataclasses import to_dict


class TestToDictDecorator:
    """Test suite for to_dict decorator."""

    def test_adds_to_dict_method(self):
        """Test that decorator adds to_dict method to class."""

        @to_dict
        @dataclass
        class TestClass:
            field1: str
            field2: int

        instance = TestClass(field1="test", field2=42)

        assert hasattr(instance, "to_dict")
        assert callable(instance.to_dict)

    def test_to_dict_returns_dict(self):
        """Test that to_dict returns a dictionary."""

        @to_dict
        @dataclass
        class TestClass:
            field1: str
            field2: int

        instance = TestClass(field1="test", field2=42)
        result = instance.to_dict()

        assert isinstance(result, dict)

    def test_to_dict_contains_all_fields(self):
        """Test that to_dict includes all dataclass fields."""

        @to_dict
        @dataclass
        class TestClass:
            field1: str
            field2: int
            field3: bool

        instance = TestClass(field1="test", field2=42, field3=True)
        result = instance.to_dict()

        assert "field1" in result
        assert "field2" in result
        assert "field3" in result
        assert result["field1"] == "test"
        assert result["field2"] == 42
        assert result["field3"] is True

    def test_to_dict_with_empty_dataclass(self):
        """Test to_dict with dataclass having no fields."""

        @to_dict
        @dataclass
        class EmptyClass:
            pass

        instance = EmptyClass()
        result = instance.to_dict()

        assert isinstance(result, dict)
        assert len(result) == 0

    def test_to_dict_with_nested_dataclass(self):
        """Test to_dict with nested dataclass."""

        @to_dict
        @dataclass
        class InnerClass:
            inner_field: str

        @to_dict
        @dataclass
        class OuterClass:
            outer_field: int
            nested: InnerClass

        inner = InnerClass(inner_field="inner")
        outer = OuterClass(outer_field=123, nested=inner)

        result = outer.to_dict()

        assert isinstance(result, dict)
        assert result["outer_field"] == 123
        assert isinstance(result["nested"], dict)
        assert result["nested"]["inner_field"] == "inner"

    def test_to_dict_with_list_field(self):
        """Test to_dict with list field."""

        @to_dict
        @dataclass
        class TestClass:
            items: list[str]

        instance = TestClass(items=["a", "b", "c"])
        result = instance.to_dict()

        assert result["items"] == ["a", "b", "c"]
        assert isinstance(result["items"], list)

    def test_to_dict_with_dict_field(self):
        """Test to_dict with dict field."""

        @to_dict
        @dataclass
        class TestClass:
            metadata: dict

        instance = TestClass(metadata={"key": "value", "count": 42})
        result = instance.to_dict()

        assert result["metadata"] == {"key": "value", "count": 42}
        assert isinstance(result["metadata"], dict)

    def test_to_dict_with_optional_fields(self):
        """Test to_dict with optional fields."""

        @to_dict
        @dataclass
        class TestClass:
            required: str
            optional: str | None = None

        instance = TestClass(required="test", optional=None)
        result = instance.to_dict()

        assert result["required"] == "test"
        assert result["optional"] is None

    def test_to_dict_with_default_values(self):
        """Test to_dict with fields having default values."""

        @to_dict
        @dataclass
        class TestClass:
            field1: str = "default"
            field2: int = 0

        instance = TestClass()
        result = instance.to_dict()

        assert result["field1"] == "default"
        assert result["field2"] == 0

    def test_to_dict_uses_dataclasses_asdict(self):
        """Test that to_dict uses dataclasses.asdict internally."""

        @to_dict
        @dataclass
        class TestClass:
            field1: str
            field2: int

        instance = TestClass(field1="test", field2=42)

        # Compare with direct asdict call
        result_to_dict = instance.to_dict()
        result_asdict = dataclasses_asdict(instance)

        assert result_to_dict == result_asdict

    def test_decorator_preserves_dataclass_functionality(self):
        """Test that decorator doesn't break dataclass features."""

        @to_dict
        @dataclass
        class TestClass:
            field1: str
            field2: int

        instance1 = TestClass(field1="test", field2=42)
        instance2 = TestClass(field1="test", field2=42)
        instance3 = TestClass(field1="other", field2=99)

        # Test equality
        assert instance1 == instance2
        assert instance1 != instance3

        # Test repr contains the expected fields
        assert "field1='test'" in repr(instance1)
        assert "field2=42" in repr(instance1)

    def test_to_dict_with_complex_types(self):
        """Test to_dict with complex type annotations."""

        @to_dict
        @dataclass
        class TestClass:
            string_field: str
            int_field: int
            float_field: float
            bool_field: bool
            list_field: list[int]
            dict_field: dict[str, str]

        instance = TestClass(
            string_field="test",
            int_field=42,
            float_field=3.14,
            bool_field=True,
            list_field=[1, 2, 3],
            dict_field={"a": "b"},
        )

        result = instance.to_dict()

        assert result["string_field"] == "test"
        assert result["int_field"] == 42
        assert result["float_field"] == 3.14
        assert result["bool_field"] is True
        assert result["list_field"] == [1, 2, 3]
        assert result["dict_field"] == {"a": "b"}

    def test_multiple_instances_have_separate_dicts(self):
        """Test that to_dict returns separate dicts for different instances."""

        @to_dict
        @dataclass
        class TestClass:
            value: int

        instance1 = TestClass(value=1)
        instance2 = TestClass(value=2)

        dict1 = instance1.to_dict()
        dict2 = instance2.to_dict()

        assert dict1["value"] == 1
        assert dict2["value"] == 2

        # Modify dict1 should not affect dict2
        dict1["value"] = 999
        assert dict2["value"] == 2

    def test_to_dict_result_is_modifiable(self):
        """Test that the returned dict can be modified without affecting instance."""

        @to_dict
        @dataclass
        class TestClass:
            field: str

        instance = TestClass(field="original")
        result = instance.to_dict()

        result["field"] = "modified"

        assert instance.field == "original"
        assert result["field"] == "modified"

    def test_decorator_can_be_applied_multiple_times(self):
        """Test that decorator works even if applied to multiple classes."""

        @to_dict
        @dataclass
        class Class1:
            field1: str

        @to_dict
        @dataclass
        class Class2:
            field2: int

        instance1 = Class1(field1="test")
        instance2 = Class2(field2=42)

        assert instance1.to_dict() == {"field1": "test"}
        assert instance2.to_dict() == {"field2": 42}
