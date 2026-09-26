import { CircleDashed, CircleDot, CircleCheckBig } from "lucide-react";

import { StatusPill } from "../../components/ui/Feedback";
import { statusLabel, statusTone } from "./progressStatus";

const ICONS = {
  not_started: CircleDashed,
  attempted: CircleDot,
  solved: CircleCheckBig,
};

/** The learner's status for a problem, in the AlgoTwin status-pill language. */
export function ProgressStatusPill({ status, showIcon = false }) {
  const Icon = ICONS[status] ?? ICONS.not_started;
  return (
    <StatusPill tone={statusTone(status)}>
      {showIcon ? <Icon aria-hidden="true" size={12} /> : null}
      {statusLabel(status)}
    </StatusPill>
  );
}

export default ProgressStatusPill;
