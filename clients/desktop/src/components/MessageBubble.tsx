import { Message } from "../App";
import "./MessageBubble.css";

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  return (
    <div className={`bubble-wrapper bubble-wrapper--${message.role}`}>
      <div className={`bubble bubble--${message.role}`}>
        <p className="bubble-content">{message.content}</p>
        {message.role === "moca" && message.agent && (
          <span className="bubble-agent">{message.agent}</span>
        )}
      </div>
    </div>
  );
}
