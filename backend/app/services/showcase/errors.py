class ShowcaseItemValidationError(ValueError):
    """A showcase item input does not satisfy the domain rules."""


class ShowcaseItemNotFoundError(Exception):
    """The requested showcase item does not belong to the salon."""


class ShowcaseMediaNotFoundError(Exception):
    """The media asset is missing, deleted, or belongs to another salon."""
