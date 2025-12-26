"""Exceptions for tags."""


class TagNotFoundError(Exception):
    """Raised when a tag is not found."""
    
    def __init__(self, tag_id: int):
        self.tag_id = tag_id
        super().__init__(f"Tag with ID {tag_id} not found")


class TagAlreadyExistsError(Exception):
    """Raised when a tag with the same name already exists in the tenant."""
    
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Tag with name '{name}' already exists")


class TagDeleteNotAllowedError(Exception):
    """Raised when a user is not allowed to delete a tag."""
    
    def __init__(self, tag_id: int):
        self.tag_id = tag_id
        super().__init__(f"Not authorized to delete tag with ID {tag_id}. Only GLOBAL_ADMIN or the tag creator can delete tags.")
