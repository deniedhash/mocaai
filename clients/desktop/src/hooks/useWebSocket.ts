import { useEffect, useRef, useState, useCallback } from "react";

export type OrbState = "idle" | "thinking" | "responding" | "error";

export interface MocaResponse {
  type: "response" | "error";
  content: string;
  agent: string;
  session_id: string;
  message?: string; // server error message
}

export interface OutgoingMessage {
  type: "text_query";
  content: string;
  session_id: string;
}

export type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

const WS_URL = "ws://localhost:8000/moca/stream";
const SESSION_ID = crypto.randomUUID();

export function useWebSocket(onMessage: (msg: MocaResponse) => void, setOrbState: (s: OrbState) => void) {
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelay = useRef(1000);
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const unmounted = useRef(false);

  const connect = useCallback(() => {
    if (unmounted.current) return;

    setStatus("connecting");
    const socket = new WebSocket(WS_URL);
    ws.current = socket;

    socket.onopen = () => {
      reconnectDelay.current = 1000;
      setStatus("connected");
    };

    socket.onmessage = (event) => {
      console.log("[MOCA WS] raw:", event.data);
      try {
        const data = JSON.parse(event.data) as MocaResponse;
        if (data.type === "response") {
          setOrbState("responding");
          onMessage(data);
          setTimeout(() => setOrbState("idle"), 2000);
        } else if (data.type === "error") {
          console.error("[MOCA WS] server error:", data.message);
          const errMsg: MocaResponse = {
            type: "response",
            content: `⚠️ ${data.message ?? "Server error"}`,
            agent: "system",
            session_id: "",
          };
          setOrbState("error");
          onMessage(errMsg);
          setTimeout(() => setOrbState("idle"), 3000);
        }
      } catch (e) {
        console.error("[MOCA WS] parse error:", e, event.data);
      }
    };

    socket.onerror = () => {
      setStatus("error");
      setOrbState("error");
    };

    socket.onclose = () => {
      if (unmounted.current) return;
      setStatus("disconnected");
      setOrbState("error");
      reconnectTimeout.current = setTimeout(() => {
        reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000);
        connect();
      }, reconnectDelay.current);
    };
  }, [onMessage, setOrbState]);

  useEffect(() => {
    unmounted.current = false;
    connect();
    return () => {
      unmounted.current = true;
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      ws.current?.close();
      ws.current = null;
    };
  }, [connect]);

  const send = useCallback((content: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      const msg: OutgoingMessage = {
        type: "text_query",
        content,
        session_id: SESSION_ID,
      };
      console.log("[MOCA WS] sending:", msg);
      ws.current.send(JSON.stringify(msg));
      setOrbState("thinking");
    } else {
      console.warn("[MOCA WS] send failed, readyState:", ws.current?.readyState);
    }
  }, [setOrbState]);

  return { send, status };
}
