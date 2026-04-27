"""
MOCA WebSocket Handler — Real-time bidirectional communication.

Endpoint: WS /moca/stream

Message types (incoming):
  text_query  → run through orchestrator → stream response back
  ping        → respond with pong

Response format (outgoing JSON):
  {"type": "response", "content": str, "agent": str, "session_id": str}
  {"type": "pong"}
  {"type": "error", "message": str}
"""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage

from memory.cache import add_message
from memory.episodic import save_interaction

router = APIRouter(tags=["websocket"])


# ---------------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Track active WebSocket connections."""

    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active[session_id] = websocket

    def disconnect(self, session_id: str):
        self.active.pop(session_id, None)

    async def send(self, session_id: str, data: dict):
        ws = self.active.get(session_id)
        if ws:
            await ws.send_text(json.dumps(data))


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/moca/stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    Real-time MOCA WebSocket endpoint.

    Each connection gets a unique session_id (or uses one from the first message).
    """
    from api.main import get_app_state
    state = get_app_state()

    session_id = str(uuid.uuid4())
    await manager.connect(session_id, websocket)

    print(f"🔌 WebSocket connected: {session_id}")

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send(session_id, {
                    "type": "error",
                    "message": "Invalid JSON payload",
                })
                continue

            msg_type = message.get("type", "")
            # Allow client to specify their own session_id
            client_session = message.get("session_id", session_id)

            if msg_type == "ping":
                await manager.send(session_id, {"type": "pong"})

            elif msg_type == "text_query":
                user_text = message.get("content", "").strip()
                if not user_text:
                    await manager.send(session_id, {
                        "type": "error",
                        "message": "Empty query content",
                    })
                    continue

                if not state["ready"] or state["graph"] is None:
                    await manager.send(session_id, {
                        "type": "error",
                        "message": "MOCA brain is not ready",
                    })
                    continue

                # Store user message
                await add_message(client_session, "user", user_text)

                # Run through orchestrator
                try:
                    graph_state = {
                        "messages": [HumanMessage(content=user_text)],
                        "session_id": client_session,
                        "routing_decision": None,
                        "agent_responses": [],
                        "conversation_history": [],
                        "final_response": None,
                    }
                    result = state["graph"].invoke(graph_state)

                    messages = result.get("messages", [])
                    last_msg = messages[-1] if messages else None

                    if last_msg is None:
                        raise ValueError("No response from orchestrator")

                    content = (
                        last_msg.content
                        if hasattr(last_msg, "content")
                        else str(last_msg)
                    )
                    agent = (
                        last_msg.additional_kwargs.get("agent", "prime")
                        if hasattr(last_msg, "additional_kwargs")
                        else "prime"
                    )

                    # Store assistant response
                    await add_message(client_session, "assistant", content)
                    await save_interaction(client_session, "user", user_text, agent="user")
                    await save_interaction(client_session, "assistant", content, agent=agent)

                    await manager.send(session_id, {
                        "type": "response",
                        "content": content,
                        "agent": agent,
                        "session_id": client_session,
                    })

                except Exception as e:
                    await manager.send(session_id, {
                        "type": "error",
                        "message": f"Orchestrator error: {str(e)}",
                    })

            else:
                await manager.send(session_id, {
                    "type": "error",
                    "message": f"Unknown message type: '{msg_type}'",
                })

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        print(f"🔌 WebSocket disconnected: {session_id}")
    except Exception as e:
        manager.disconnect(session_id)
        print(f"⚠️  WebSocket error [{session_id}]: {e}")
