import { Link } from "react-router-dom";

import BrandMark from "../../components/layout/BrandMark";

export default function AuthLayout({ eyebrow, title, description, children, footer }) {
  return (
    <div className="auth-page">
      <div className="auth-glow" />
      <section className="auth-panel">
        <Link className="auth-brand" to="/dashboard">
          <BrandMark />
        </Link>
        <div className="auth-heading">
          <span className="eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        {children}
        <div className="auth-footer">{footer}</div>
      </section>
    </div>
  );
}
