# ruff: noqa: PLR2004
import pytest
from pydantic import ValidationError

from project.dtos.tag import CreateTagDTO, TagDTO, UpdateTagDTO
from project.schemas.tag import (
    CreateTagSchema,
    TagListSchema,
    TagSchema,
    UpdateTagSchema,
)


def test_tag_dtos_preserve_input_fields_and_update_defaults():
    created = CreateTagDTO('Brand', 'Branding content', '#AABBCC')
    updated = UpdateTagDTO()

    assert (created.label, created.description, created.color) == (
        'Brand',
        'Branding content',
        '#AABBCC',
    )
    assert (updated.label, updated.description, updated.color) == (
        None,
        None,
        None,
    )


def test_tag_schema_converts_dto_and_list_schema_wraps_items():
    dto = TagDTO(9, 2, 'Brand', 'Branding content', '#AABBCC')

    result = TagSchema.from_dto(dto)
    listing = TagListSchema(items=[result])

    assert result.model_dump() == {
        'id': 9,
        'project_id': 2,
        'label': 'Brand',
        'description': 'Branding content',
        'color': '#AABBCC',
    }
    assert listing.items == [result]


def test_create_tag_schema_accepts_hex_color_and_label_boundary():
    result = CreateTagSchema(
        label='x' * 128,
        description='d' * 256,
        color='#a1B2c3',
    )

    assert len(result.label) == 128
    assert len(result.description) == 256
    assert result.color == '#a1B2c3'


@pytest.mark.parametrize(
    'payload',
    [
        {'label': '', 'description': 'Text', 'color': '#AABBCC'},
        {'label': 'x' * 129, 'description': 'Text', 'color': '#AABBCC'},
        {'label': 'Brand', 'description': 'Text', 'color': 'AABBCC'},
        {'label': 'Brand', 'description': 'Text', 'color': '#12345'},
    ],
)
def test_create_tag_schema_rejects_invalid_label_or_color(payload):
    with pytest.raises(ValidationError):
        CreateTagSchema(**payload)


def test_update_tag_schema_accepts_partial_changes():
    result = UpdateTagSchema(color='#ABCDEF')

    assert result.label is None
    assert result.description is None
    assert result.color == '#ABCDEF'


def test_update_tag_schema_rejects_invalid_partial_color():
    with pytest.raises(ValidationError):
        UpdateTagSchema(color='blue')
