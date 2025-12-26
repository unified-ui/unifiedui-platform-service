"""Unit tests for unifiedui/utils/api_query.py"""
import pytest
from dataclasses import fields

from unifiedui.utils.api_query import APIFilterQuery


class TestAPIFilterQuery:
    """Test suite for APIFilterQuery dataclass."""
    
    def test_default_initialization(self):
        """Test that APIFilterQuery has correct default values."""
        query = APIFilterQuery()
        
        assert query.select == ""
        assert query.top == 100
        assert query.skip == 0
        assert query.search == ""
        assert query.order_by == ""
        assert query.filter_ == ""
        assert query.count is False
        assert query.expand is False
        assert query.next_link == ""
    
    def test_custom_initialization(self):
        """Test APIFilterQuery with custom values."""
        query = APIFilterQuery(
            select="id,name",
            top=50,
            skip=10,
            search="test",
            order_by="created_at",
            filter_="status eq 'active'",
            count=True,
            expand=True,
            next_link="https://api.example.com/next"
        )
        
        assert query.select == "id,name"
        assert query.top == 50
        assert query.skip == 10
        assert query.search == "test"
        assert query.order_by == "created_at"
        assert query.filter_ == "status eq 'active'"
        assert query.count is True
        assert query.expand is True
        assert query.next_link == "https://api.example.com/next"
    
    def test_partial_initialization(self):
        """Test APIFilterQuery with only some values set."""
        query = APIFilterQuery(top=25, skip=5)
        
        assert query.select == ""
        assert query.top == 25
        assert query.skip == 5
        assert query.search == ""
        assert query.order_by == ""
        assert query.filter_ == ""
        assert query.count is False
        assert query.expand is False
        assert query.next_link == ""
    
    def test_is_dataclass(self):
        """Test that APIFilterQuery is a dataclass."""
        query = APIFilterQuery()
        assert hasattr(query, '__dataclass_fields__')
    
    def test_field_metadata_exists(self):
        """Test that fields have metadata with descriptions."""
        query_fields = fields(APIFilterQuery)
        
        for field in query_fields:
            assert "description" in field.metadata
            assert isinstance(field.metadata["description"], str)
            assert len(field.metadata["description"]) > 0
    
    def test_select_field_metadata(self):
        """Test select field has correct metadata."""
        query_fields = {f.name: f for f in fields(APIFilterQuery)}
        select_field = query_fields["select"]
        
        assert select_field.metadata["description"] == "Fields to select in the results"
        assert select_field.default == ""
    
    def test_top_field_metadata(self):
        """Test top field has correct metadata."""
        query_fields = {f.name: f for f in fields(APIFilterQuery)}
        top_field = query_fields["top"]
        
        assert top_field.metadata["description"] == "Maximum number of items to return"
        assert top_field.default == 100
    
    def test_skip_field_metadata(self):
        """Test skip field has correct metadata."""
        query_fields = {f.name: f for f in fields(APIFilterQuery)}
        skip_field = query_fields["skip"]
        
        assert skip_field.metadata["description"] == "Number of items to skip"
        assert skip_field.default == 0
    
    def test_search_field_metadata(self):
        """Test search field has correct metadata."""
        query_fields = {f.name: f for f in fields(APIFilterQuery)}
        search_field = query_fields["search"]
        
        assert search_field.metadata["description"] == "Search term to filter results"
        assert search_field.default == ""
    
    def test_order_by_field_metadata(self):
        """Test order_by field has correct metadata."""
        query_fields = {f.name: f for f in fields(APIFilterQuery)}
        order_by_field = query_fields["order_by"]
        
        assert order_by_field.metadata["description"] == "Field to order results by"
        assert order_by_field.default == ""
    
    def test_filter_field_metadata(self):
        """Test filter_ field has correct metadata."""
        query_fields = {f.name: f for f in fields(APIFilterQuery)}
        filter_field = query_fields["filter_"]
        
        assert filter_field.metadata["description"] == "Filter expression to filter results"
        assert filter_field.default == ""
    
    def test_count_field_metadata(self):
        """Test count field has correct metadata."""
        query_fields = {f.name: f for f in fields(APIFilterQuery)}
        count_field = query_fields["count"]
        
        assert count_field.metadata["description"] == "Whether to include a count of total items"
        assert count_field.default is False
    
    def test_expand_field_metadata(self):
        """Test expand field has correct metadata."""
        query_fields = {f.name: f for f in fields(APIFilterQuery)}
        expand_field = query_fields["expand"]
        
        assert expand_field.metadata["description"] == "Related entities to expand in the results"
        assert expand_field.default is False
    
    def test_next_link_field_metadata(self):
        """Test next_link field has correct metadata."""
        query_fields = {f.name: f for f in fields(APIFilterQuery)}
        next_link_field = query_fields["next_link"]
        
        assert next_link_field.metadata["description"] == "Link to the next page of results"
        assert next_link_field.default == ""
    
    def test_mutation_of_fields(self):
        """Test that query fields can be modified after creation."""
        query = APIFilterQuery()
        
        query.top = 200
        query.skip = 50
        query.search = "updated"
        
        assert query.top == 200
        assert query.skip == 50
        assert query.search == "updated"
    
    def test_pagination_scenario(self):
        """Test typical pagination scenario."""
        # First page
        first_page = APIFilterQuery(top=10, skip=0)
        assert first_page.top == 10
        assert first_page.skip == 0
        
        # Second page
        second_page = APIFilterQuery(top=10, skip=10)
        assert second_page.top == 10
        assert second_page.skip == 10
    
    def test_search_and_filter_scenario(self):
        """Test search and filter combined."""
        query = APIFilterQuery(
            search="John",
            filter_="age gt 18 and city eq 'Munich'",
            order_by="lastName"
        )
        
        assert query.search == "John"
        assert query.filter_ == "age gt 18 and city eq 'Munich'"
        assert query.order_by == "lastName"
    
    def test_field_types(self):
        """Test that fields have correct types."""
        query = APIFilterQuery()
        
        assert isinstance(query.select, str)
        assert isinstance(query.top, int)
        assert isinstance(query.skip, int)
        assert isinstance(query.search, str)
        assert isinstance(query.order_by, str)
        assert isinstance(query.filter_, str)
        assert isinstance(query.count, bool)
        assert isinstance(query.expand, bool)
        assert isinstance(query.next_link, str)
    
    def test_equality(self):
        """Test that two queries with same values are equal."""
        query1 = APIFilterQuery(top=50, skip=10, search="test")
        query2 = APIFilterQuery(top=50, skip=10, search="test")
        
        assert query1 == query2
    
    def test_inequality(self):
        """Test that two queries with different values are not equal."""
        query1 = APIFilterQuery(top=50, skip=10)
        query2 = APIFilterQuery(top=100, skip=10)
        
        assert query1 != query2
