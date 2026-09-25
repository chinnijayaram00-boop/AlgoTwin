import { ArrowLeft, Compass } from "lucide-react";
import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="not-found">
      <div className="not-found-icon"><Compass size={30} /></div>
      <span className="eyebrow">Route not found</span>
      <h2>That path is still being mapped.</h2>
      <p>Return to the overview and continue building your learning loop.</p>
      <Link className="button button-primary" to="/dashboard"><ArrowLeft size={16} /> Back to overview</Link>
    </div>
  );
}
