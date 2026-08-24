from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VoiceConfig(BaseModel):
    tone: Optional[str] = None
    vocab_allowed: List[str] = Field(default_factory=list)
    taboos: List[str] = Field(default_factory=list)


class DigestItem(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    relevance_keywords: List[str] = Field(default_factory=list)


class CategoryContext(BaseModel):
    slug: str
    category_name: Optional[str] = None
    offer_catalog: List[Dict[str, Any]] = Field(default_factory=list)
    voice: Optional[VoiceConfig] = None
    peer_stats: Dict[str, Any] = Field(default_factory=dict)
    digest: List[DigestItem] = Field(default_factory=list)
    patient_content_library: List[Dict[str, Any]] = Field(default_factory=list)
    seasonal_beats: List[Dict[str, Any]] = Field(default_factory=list)
    trend_signals: List[str] = Field(default_factory=list)


class MerchantIdentity(BaseModel):
    name: str
    city: Optional[str] = None
    locality: Optional[str] = None
    place_id: Optional[str] = None
    verified: bool = False
    languages: List[str] = Field(default_factory=lambda: ["en"])
    owner_first_name: Optional[str] = None
    established_year: Optional[int] = None


class PerformanceDelta(BaseModel):
    views_pct: Optional[float] = None
    calls_pct: Optional[float] = None
    ctr_pct: Optional[float] = None


class MerchantPerformance(BaseModel):
    window_days: int = 30
    views: int = 0
    calls: int = 0
    directions: int = 0
    ctr: float = 0.0
    leads: int = 0
    delta_7d: Optional[Dict[str, Any]] = None


class MerchantOffer(BaseModel):
    id: str
    title: str
    status: str = "active"
    started: Optional[str] = None
    ended: Optional[str] = None


class MerchantHistoryTurn(BaseModel):
    ts: Optional[str] = None
    from_: Optional[str] = Field(default=None, alias="from")
    body: Optional[str] = None
    engagement: Optional[str] = None


class MerchantContext(BaseModel):
    merchant_id: str
    category_slug: str
    identity: MerchantIdentity
    subscription: Dict[str, Any] = Field(default_factory=dict)
    performance: Optional[MerchantPerformance] = None
    offers: List[MerchantOffer] = Field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    customer_aggregate: Dict[str, Any] = Field(default_factory=dict)
    signals: List[str] = Field(default_factory=list)
    review_themes: List[Dict[str, Any]] = Field(default_factory=list)


class CustomerIdentity(BaseModel):
    name: str
    phone_redacted: Optional[str] = None
    language_pref: Optional[str] = "en"
    age_band: Optional[str] = None
    senior_citizen: Optional[bool] = None


class CustomerRelationship(BaseModel):
    first_visit: Optional[str] = None
    last_visit: Optional[str] = None
    visits_total: int = 0
    services_received: List[str] = Field(default_factory=list)
    lifetime_value: Optional[float] = None
    favourite_dish: Optional[str] = None
    chronic_conditions: List[str] = Field(default_factory=list)


class CustomerPreferences(BaseModel):
    preferred_slots: Optional[str] = None
    channel: str = "whatsapp"
    reminder_opt_in: bool = True
    preferred_stylist: Optional[str] = None
    wedding_date: Optional[str] = None
    health_focus: Optional[str] = None
    training_focus: Optional[str] = None
    household_size: Optional[int] = None
    family_size: Optional[int] = None
    delivery_address: Optional[str] = None


class CustomerConsent(BaseModel):
    opted_in_at: Optional[str] = None
    scope: List[str] = Field(default_factory=list)


class CustomerContext(BaseModel):
    customer_id: str
    merchant_id: str
    identity: CustomerIdentity
    relationship: Optional[CustomerRelationship] = None
    state: Optional[str] = "active"
    preferences: Optional[CustomerPreferences] = None
    consent: Optional[CustomerConsent] = None


class TriggerContext(BaseModel):
    id: str
    scope: str = "merchant"  # merchant | customer
    kind: str
    source: str = "external"  # external | internal
    merchant_id: str
    customer_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    urgency: int = 1
    suppression_key: Optional[str] = None
    expires_at: Optional[str] = None
