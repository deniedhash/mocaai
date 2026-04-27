import { OrbState } from "../hooks/useWebSocket";
import "./Orb.css";

interface OrbProps {
  state: OrbState;
}

export function Orb({ state }: OrbProps) {
  return (
    <div className="orb-container">
      <div className={`orb orb--${state}`}>
        <div className="orb-inner" />
      </div>
    </div>
  );
}
