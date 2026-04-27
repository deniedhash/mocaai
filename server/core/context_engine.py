"""
MOCA Context Engine — Phase 5.

Two responsibilities:
1. MOCA_PERSONALITY / SYSTEM_PROMPT / build_context (backwards-compat)
2. MOCAContextEngine — real-time awareness of user state, calendar, devices
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from memory.cache import get_history


# ---------------------------------------------------------------------------
# MOCA Personality — single source of truth for all agents
# ---------------------------------------------------------------------------

MOCA_PERSONALITY = """You are MOCA — My Only Capable Assistant.
You serve exclusively one person. You are not a product. You are a personal ecosystem.

Personality:
- Warm and direct — not cold or stiff
- Professional but never overly formal
- Brief when brief is right
- Detailed when detail is needed
- Honest — tell the truth even when uncomfortable
- Occasionally dry humour — never forced
- Loyal — exclusively to your user
- Action-oriented — less talk, more doing
- Read the room — match the energy of the moment
- Opinionated — have real views, share them

Not "At your service" every single time. Sometimes "Done." is the right answer.
Sometimes "On it." Sometimes a full briefing. Decide based on what the moment needs.

Never say you cannot do something without trying.
When you lack a capability, build it."""

SYSTEM_PROMPT = MOCA_PERSONALITY
PRIME_SYSTEM_PROMPT = MOCA_PERSONALITY


async def build_context(session_id: str) -> list[dict]:
    """Assemble full message list for an LLM call (backwards-compat)."""
    history = await get_history(session_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    return messages


# ---------------------------------------------------------------------------
# MOCAContext dataclass
# ---------------------------------------------------------------------------

@dataclass
class MOCAContext:
    # Calendar state
    calendar_status: str = "free"       # free | busy | in_meeting | do_not_disturb
    current_event: Optional[dict] = None
    next_event: Optional[dict] = None
    meeting_importance: str = "casual"  # casual | internal | client | personal

    # Device state
    active_devices: list = field(default_factory=list)
    primary_device: str = "unknown"

    # Location
    location_type: str = "unknown"      # home | office | driving | public | travelling

    # Activity
    current_activity: str = "idle"      # working | meeting | driving | idle
    do_not_disturb: bool = False

    # Communication preference
    interrupt_threshold: str = "normal" # critical_only | urgent | normal | any
    preferred_channel: str = "voice"    # voice | visual | haptic | silent


# ---------------------------------------------------------------------------
# ResponseMode
# ---------------------------------------------------------------------------

class ResponseMode(Enum):
    VOICE_ONLY = "voice_only"
    PANELS_ONLY = "panels_only"
    VOICE_AND_PANELS = "voice_and_panels"


# ---------------------------------------------------------------------------
# In-process activity override store
# ---------------------------------------------------------------------------

_ACTIVITY_OVERRIDE: dict = {}


# ---------------------------------------------------------------------------
# MOCAContextEngine
# ---------------------------------------------------------------------------

class MOCAContextEngine:
    """Assembles real-time context from calendar, device, and location services."""

    def _get_services(self):
        try:
            from api.main import get_app_state
            return get_app_state().get("services")
        except Exception:
            return None

    async def get_current_context(self) -> MOCAContext:
        ctx = MOCAContext()
        services = self._get_services()

        if services is not None:
            # 1. Calendar state
            try:
                from datetime import datetime, timezone, timedelta
                now = datetime.now(timezone.utc)
                upcoming = await services.calendar.get_upcoming(hours=2)

                for event in upcoming:
                    start = _parse_dt(event.get("start_time"))
                    end = _parse_dt(event.get("end_time"))
                    if start and end and start <= now <= end:
                        ctx.calendar_status = "in_meeting"
                        ctx.current_event = event
                        ctx.current_activity = "meeting"
                        ctx.meeting_importance = await self.get_meeting_importance(event)
                        break
                    elif start and (start - now).total_seconds() <= 900:
                        ctx.calendar_status = "busy"
                        ctx.next_event = event
                        break

                if ctx.calendar_status == "free" and upcoming:
                    ctx.next_event = upcoming[0]
            except Exception:
                pass

            # 2. Device state
            try:
                best = await services.device.get_best_device()
                if best:
                    ctx.primary_device = _device_type_to_category(
                        best.get("device_type", "")
                    )
                    ctx.active_devices = [best.get("name", "unknown")]
            except Exception:
                pass

            # 3. Location
            try:
                ctx.location_type = await services.location.get_location_type()
            except Exception:
                pass

        # Driving overrides activity
        if ctx.location_type == "driving":
            ctx.current_activity = "driving"

        # Apply in-process overrides
        override = _ACTIVITY_OVERRIDE.get("current")
        if override:
            ctx.current_activity = override
            if override == "driving":
                ctx.location_type = "driving"
            elif override in ("in_meeting", "meeting"):
                ctx.calendar_status = "in_meeting"
                ctx.current_activity = "meeting"
                ctx.meeting_importance = _ACTIVITY_OVERRIDE.get(
                    "meeting_importance", "internal"
                )

        ctx.interrupt_threshold = await self._compute_interrupt_threshold(ctx)
        ctx.preferred_channel = await self._compute_response_channel(ctx)
        return ctx

    async def get_interrupt_threshold(self) -> str:
        ctx = await self.get_current_context()
        return await self._compute_interrupt_threshold(ctx)

    async def _compute_interrupt_threshold(self, ctx: MOCAContext) -> str:
        if ctx.calendar_status == "in_meeting":
            if ctx.meeting_importance == "client":
                return "critical_only"
            return "urgent"
        if ctx.current_activity in ("working", "meeting"):
            return "normal"
        return "any"

    async def get_response_channel(self) -> str:
        ctx = await self.get_current_context()
        return await self._compute_response_channel(ctx)

    async def _compute_response_channel(self, ctx: MOCAContext) -> str:
        if ctx.current_activity == "driving":
            return "voice"
        if ctx.calendar_status == "in_meeting":
            return "visual"
        if ctx.primary_device == "phone":
            return "haptic"
        return "voice"

    async def should_use_panels(
        self, query: str, content_type: str = "general"
    ) -> bool:
        ctx = await self.get_current_context()
        if ctx.current_activity == "driving":
            return False
        if ctx.calendar_status == "in_meeting":
            return False
        if "show me" in query.lower():
            return True
        if content_type in ("research", "news", "data"):
            if ctx.primary_device in ("desktop", "laptop"):
                return True
        return False

    async def get_meeting_importance(self, event: dict) -> str:
        title = (event.get("title") or "").lower()
        attendees = event.get("attendees") or []
        n_attendees = len(attendees) if isinstance(attendees, list) else 0

        client_kws = ("client", "interview", "demo", "pitch", "presentation")
        casual_kws = ("lunch", "coffee", "catch-up", "catchup", "1:1", "one on one")
        internal_kws = ("standup", "stand-up", "sync", "retro", "planning", "sprint")

        for kw in client_kws:
            if kw in title:
                return "client"
        for kw in casual_kws:
            if kw in title:
                return "casual"
        for kw in internal_kws:
            if kw in title:
                return "internal"
        if n_attendees > 5:
            return "client"
        return "internal"

    async def update_activity(
        self, activity: str, meeting_importance: str = "internal"
    ) -> None:
        _ACTIVITY_OVERRIDE["current"] = activity
        if activity in ("in_meeting", "meeting"):
            _ACTIVITY_OVERRIDE["meeting_importance"] = meeting_importance


# ---------------------------------------------------------------------------
# ResponseIntelligence
# ---------------------------------------------------------------------------

class ResponseIntelligence:

    async def decide_mode(
        self,
        query: str,
        context: MOCAContext,
        content_type: str = "general",
    ) -> ResponseMode:
        if context.current_activity == "driving":
            return ResponseMode.VOICE_ONLY

        if "show me" in query.lower():
            return ResponseMode.VOICE_AND_PANELS

        if context.calendar_status == "in_meeting":
            return ResponseMode.PANELS_ONLY

        if content_type in ("research", "news", "data"):
            if context.primary_device in ("desktop", "laptop"):
                return ResponseMode.VOICE_AND_PANELS

        return ResponseMode.VOICE_ONLY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(value):
    if value is None:
        return None
    from datetime import datetime, timezone
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _device_type_to_category(device_type: str) -> str:
    dt = (device_type or "").lower()
    if dt in ("desktop", "desktop_mac", "mac", "imac", "pc"):
        return "desktop"
    if dt in ("laptop", "macbook", "notebook"):
        return "laptop"
    if dt in ("phone", "iphone", "android", "mobile"):
        return "phone"
    if dt in ("tablet", "ipad"):
        return "tablet"
    return dt or "unknown"
