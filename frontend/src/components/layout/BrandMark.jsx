import { Command } from "lucide-react";

export default function BrandMark() {
  return (
    <div className="brand-mark" aria-label="ALgotwin">
      <span className="brand-symbol">
        <Command size={17} strokeWidth={2.5} />
      </span>
      <span className="brand-wordmark">ALgotwin</span>
    </div>
  );
}
