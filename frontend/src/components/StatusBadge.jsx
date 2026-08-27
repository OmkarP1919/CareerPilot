import { getStatusClass } from "../utils/constants";

export default function StatusBadge({ status }) {
  return (
    <span className={`status-badge ${getStatusClass(status)}`} role="status">
      {status}
    </span>
  );
}
