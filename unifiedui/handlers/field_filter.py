"""Utility for filtering response fields and parsing bulk ID queries."""

from __future__ import annotations

from typing import overload

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

ALWAYS_INCLUDE_FIELDS: set[str] = {"id", "my_permission"}


def filter_response_fields[T: BaseModel](
    data: list[T] | T,
    fields: str | None,
    always_include: set[str] | None = None,
) -> list[dict[str, object]] | dict[str, object] | list[T] | T:
    """Filter response data to include only the requested fields.

    If ``fields`` is None the data is returned unchanged (full response).
    Otherwise, the comma-separated field names are validated against the
    model and only the requested fields (plus ``always_include``) are
    returned via ``model_dump(include=...)``.

    Args:
        data: A single Pydantic model or a list of Pydantic models.
        fields: Comma-separated field names to include, or None for all.
        always_include: Fields that are always included regardless of the
            ``fields`` selection.  Defaults to ``{"id", "my_permission"}``.

    Returns:
        Filtered dict(s) when ``fields`` is set, original model(s) otherwise.

    Raises:
        HTTPException: If any requested field name is invalid.
    """
    if fields is None:
        return data

    if always_include is None:
        always_include = ALWAYS_INCLUDE_FIELDS

    requested = {f.strip() for f in fields.split(",") if f.strip()}
    if not requested:
        return data

    if isinstance(data, list) and not data:
        return data

    sample = data[0] if isinstance(data, list) else data
    valid_fields = set(sample.model_fields.keys())
    invalid = requested - valid_fields
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid field names: {', '.join(sorted(invalid))}. "
            f"Valid fields: {', '.join(sorted(valid_fields))}",
        )

    include = (requested | always_include) & valid_fields

    if isinstance(data, list):
        return [item.model_dump(include=include, mode="json") for item in data]
    return data.model_dump(include=include, mode="json")


@overload
def filtered_response[T: BaseModel](
    data: list[T],
    fields: str | None,
    always_include: set[str] | None = None,
) -> JSONResponse | list[T]: ...


@overload
def filtered_response[T: BaseModel](
    data: T,
    fields: str | None,
    always_include: set[str] | None = None,
) -> JSONResponse | T: ...


def filtered_response[T: BaseModel](
    data: list[T] | T,
    fields: str | None,
    always_include: set[str] | None = None,
) -> JSONResponse | list[T] | T:
    """Filter response fields and return JSONResponse when filtering is active.

    Use this instead of ``filter_response_fields`` in route handlers to
    bypass FastAPI response model validation when fields are filtered.

    Args:
        data: A single Pydantic model or a list of Pydantic models.
        fields: Comma-separated field names to include, or None for all.
        always_include: Fields that are always included regardless of the
            ``fields`` selection.

    Returns:
        JSONResponse with filtered data when ``fields`` is set,
        original model(s) otherwise.
    """
    if fields is None:
        return data
    filtered = filter_response_fields(data, fields, always_include)
    return JSONResponse(content=filtered)


def parse_ids(ids: str | None) -> list[str] | None:
    """Parse a comma-separated string of IDs into a list.

    Args:
        ids: Comma-separated ID string, or None.

    Returns:
        List of non-empty ID strings, or None if input is None.
    """
    if ids is None:
        return None
    return [i.strip() for i in ids.split(",") if i.strip()]
