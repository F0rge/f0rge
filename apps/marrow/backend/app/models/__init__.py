from __future__ import annotations

from app.models.user import User
from app.models.entry import Entry
from app.models.health_metrics import HealthMetric
from app.models.meal import Meal
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_diet_tag import PhotoDietTag
from app.models.photo_ingredient import PhotoIngredient
from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias
from app.models.session import AuthSession
from app.models.diet_tag_catalog import DietTagCatalogItem
from app.models.medication_catalog import MedicationCatalogItem
from app.models.supplement_catalog import SupplementCatalogItem
from app.models.symptom_catalog import SymptomCatalogItem
from app.models.treatment import Treatment
from app.models.treatment_log import TreatmentLog
from app.models.weather import WeatherReading
from app.models.lab import Lab
from app.models.lab_marker_catalog import LabMarkerCatalog
from app.models.lab_marker_alias import LabMarkerAlias
from app.models.lab_marker import LabMarker
from app.models.user_settings import UserSettings
from app.models.embedding import Embedding
from app.models.embedding_queue import EmbeddingQueue
from app.models.tracker import Tracker
from app.models.tracker_log import TrackerLog
from app.models.notification import Notification
from app.models.connection import Connection
from app.models.group import Group, GroupMember
from app.models.meal_tag import MealTag
from app.models.device_token import DeviceToken
import app.models.events  # noqa: F401 — register ORM insert hooks

__all__ = [
    "User",
    "Entry",
    "Meal",
    "Photo",
    "PhotoAnalysis",
    "PhotoDietTag",
    "PhotoIngredient",
    "DietaryIngredient",
    "IngredientAlias",
    "AuthSession",
    "WeatherReading",
    "HealthMetric",
    "DietTagCatalogItem",
    "MedicationCatalogItem",
    "SupplementCatalogItem",
    "SymptomCatalogItem",
    "Treatment",
    "TreatmentLog",
    "Lab",
    "LabMarkerCatalog",
    "LabMarkerAlias",
    "LabMarker",
    "UserSettings",
    "Embedding",
    "EmbeddingQueue",
    "Tracker",
    "TrackerLog",
    "Notification",
    "Connection",
    "Group",
    "GroupMember",
    "MealTag",
    "DeviceToken",
]
