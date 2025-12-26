from dataclasses import dataclass, field


@dataclass
class APIFilterQuery:
    select: str = field(default="", metadata={"description": "Fields to select in the results"})
    top: int = field(default=100, metadata={"description": "Maximum number of items to return"})
    skip: int = field(default=0, metadata={"description": "Number of items to skip"})
    search: str = field(default="", metadata={"description": "Search term to filter results"})
    order_by: str = field(default="", metadata={"description": "Field to order results by"})
    filter_: str = field(default="", metadata={"description": "Filter expression to filter results"})
    count: bool = field(default=False, metadata={"description": "Whether to include a count of total items"})
    expand: bool = field(default=False, metadata={"description": "Related entities to expand in the results"})
    next_link: str = field(default="", metadata={"description": "Link to the next page of results"})
