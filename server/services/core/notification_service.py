"""
MOCA Notification Service — Phase 1 stub.

Phase 2 will implement:
- Push notifications (FCM, APNs)
- In-app toast notifications via WebSocket
- Email notification dispatch
- Slack/Discord webhooks
"""

from typing import Optional


async def notify(
    session_id: str,
    message: str,
    channel: str = "websocket",
    metadata: Optional[dict] = None,
) -> bool:
    """
    Dispatch a notification to the user.

    Args:
        session_id: Target session/device identifier.
        message: Notification content.
        channel: Delivery channel ('websocket', 'push', 'email').
        metadata: Optional channel-specific metadata.

    Returns:
        True if dispatched successfully, False otherwise.

    Phase 1: no-op stub, always returns True.
    """
    print(f"[NotificationService] [{channel}] → {session_id}: {message[:60]}")
    return True
