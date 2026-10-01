import {
  Bug,
  CircleCheckBig,
  CircleDot,
  CircleSlash,
  CircleX,
  Clock3,
  Cpu,
  Timer,
  Wrench,
} from "lucide-react";

import { StatusPill } from "../../components/ui/Feedback";
import { statusLabel, statusTone } from "./submissionStatus";

const ICONS = {
  queued: Clock3,
  running: CircleDot,
  accepted: CircleCheckBig,
  wrong_answer: CircleX,
  runtime_error: Bug,
  compilation_error: Wrench,
  time_limit_exceeded: Timer,
  memory_limit_exceeded: Cpu,
  failed: CircleSlash,
};

/** A submission's stored status, in the AlgoTwin status-pill language. */
export function SubmissionStatusPill({ status, showIcon = false }) {
  const Icon = ICONS[status] ?? ICONS.queued;
  return (
    <StatusPill tone={statusTone(status)}>
      {showIcon ? <Icon aria-hidden="true" size={12} /> : null}
      {statusLabel(status)}
    </StatusPill>
  );
}

export default SubmissionStatusPill;
