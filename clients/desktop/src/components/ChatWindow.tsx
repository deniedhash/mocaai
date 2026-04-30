import { useEffect, useRef, useState, KeyboardEvent } from "react";
import { Message } from "../App";
import { MessageBubble } from "./MessageBubble";
import { ConnectionStatus } from "../hooks/useWebSocket";
import "./ChatWindow.css";

interface ChatWindowProps {
  messages: Message[];
  status: ConnectionStatus;
  onSend: (content: string) => void;
  isTyping: boolean;
}

export function ChatWindow({ messages, status, onSend, isTyping }: ChatWindowProps) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  useEffect(() => {
    const handleWindowFocus = () => inputRef.current?.focus();
    window.addEventListener("focus", handleWindowFocus);
    return () => window.removeEventListener("focus", handleWindowFocus);
  }, []);

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && input.trim()) {
      onSend(input.trim());
      setInput("");
    }
  };

  return (
    <div className="chat-window" data-tauri-drag-region>
      <div className="chat-header" data-tauri-drag-region>
        <span className="chat-title" data-tauri-drag-region>MOCA</span>
        <span className={`status-dot status-dot--${status}`} title={status} />
      </div>

      <div className="chat-messages">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {isTyping && (
          <div className="bubble-wrapper bubble-wrapper--moca">
            <div className="bubble bubble--moca typing-indicator">
              <span /><span /><span />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-row">
        <input
          ref={inputRef}
          className="chat-input"
          type="text"
          placeholder="Ask MOCA anything..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          autoFocus
        />
      </div>
    </div>
  );
}
