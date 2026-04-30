import { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Orb } from "./components/Orb";
import { ChatWindow } from "./components/ChatWindow";
import { useWebSocket, OrbState, MocaResponse } from "./hooks/useWebSocket";
import "./App.css";

export interface Message {
  id: string;
  role: "user" | "moca";
  content: string;
  agent?: string;
  timestamp: Date;
}

const MAX_MESSAGES = 50;

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [orbState, setOrbState] = useState<OrbState>("idle");
  const [isTyping, setIsTyping] = useState(false);

  const handleMocaMessage = useCallback((data: MocaResponse) => {
    setIsTyping(false);
    setMessages((prev) => {
      const next = [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "moca" as const,
          content: data.content,
          agent: data.agent,
          timestamp: new Date(),
        },
      ];
      return next.slice(-MAX_MESSAGES);
    });
  }, []); 

  const { send, status } = useWebSocket(handleMocaMessage, setOrbState);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        invoke("hide_window").catch(() => {});
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleSend = useCallback((content: string) => {
    setMessages((prev) => {
      const next = [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "user" as const,
          content,
          timestamp: new Date(),
        },
      ];
      return next.slice(-MAX_MESSAGES);
    });
    setIsTyping(true);
    send(content);
  }, [send]);

  return (
    <div className="app">
      <Orb state={orbState} />
      <ChatWindow messages={messages} status={status} onSend={handleSend} isTyping={isTyping} />
    </div>
  );
}
