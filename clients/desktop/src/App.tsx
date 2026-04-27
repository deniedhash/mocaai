import { useCallback, useState } from "react";
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

  const handleMocaMessage = useCallback((data: MocaResponse) => {
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
    send(content);
  }, [send]);

  return (
    <div className="app">
      <Orb state={orbState} />
      <ChatWindow messages={messages} status={status} onSend={handleSend} />
    </div>
  );
}
