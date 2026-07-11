from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CatalogSuggestionItem(BaseModel):
    key: str
    label: str


class TrackerSuggestionItem(BaseModel):
    name: str
    kind: str
    icon: str | None = None
    unit: str | None = None


class CatalogSuggestionsResponse(BaseModel):
    symptoms: list[CatalogSuggestionItem]
    medications: list[CatalogSuggestionItem]
    supplements: list[CatalogSuggestionItem]
    trackers: list[TrackerSuggestionItem]
    bulk_supplements: list[CatalogSuggestionItem]
    bulk_medications: list[CatalogSuggestionItem]


class CatalogSetupRequest(BaseModel):
    symptoms: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
    trackers: list[str] = Field(default_factory=list)


class CatalogSetupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symptoms_created: int
    medications_created: int
    supplements_created: int
    trackers_created: int
