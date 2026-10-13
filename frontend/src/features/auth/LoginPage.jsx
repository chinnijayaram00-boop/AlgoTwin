import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ErrorState } from "../../components/ui/Feedback";
import { AUTH_ROUTES, resolveDestination } from "./authPolicy";
import { authService } from "./authService";
import AuthLayout from "./AuthLayout";
import { useAuth } from "./useAuth";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validateLogin({ email, password }) {
  const normalizedEmail = email.trim();

  if (!normalizedEmail) {
    return "Enter your email address.";
  }
  if (!EMAIL_PATTERN.test(normalizedEmail)) {
    return "Enter a valid email address.";
  }
  if (!password.trim()) {
    return "Enter your password to continue.";
  }
  return "";
}

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const destination = resolveDestination(location.state);

  function handleChange(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
    setError("");
  }

  async function handleSubmit(event) {
    event.preventDefault();

    const message = validateLogin(form);
    if (message) {
      setError(message);
      return;
    }

    setError("");
    setSubmitting(true);
    try {
      const payload = await authService.login({ email: form.email.trim(), password: form.password });
      login(payload);
      navigate(destination, { replace: true });
    } catch (requestError) {
      setError(requestError?.message || "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      description="Sign in to keep your solved problems, submissions, and progress in sync."
      eyebrow="Welcome back"
      footer={
        <>
          <span>New to ALgotwin?</span>
          <Link to={AUTH_ROUTES.register}>Create an account</Link>
        </>
      }
      title="Sign in to your workspace."
    >
      <form className="auth-form" noValidate onSubmit={handleSubmit}>
        <label className="auth-field">
          <span>Email</span>
          <input
            autoComplete="email"
            autoFocus
            name="email"
            onChange={handleChange}
            placeholder="you@example.com"
            required
            type="email"
            value={form.email}
          />
        </label>
        <label className="auth-field">
          <span>Password</span>
          <input
            autoComplete="current-password"
            name="password"
            onChange={handleChange}
            placeholder="Your password"
            required
            type="password"
            value={form.password}
          />
        </label>
        {error ? <ErrorState message={error} /> : null}
        <button className="button button-primary auth-submit" disabled={submitting} type="submit">
          {submitting ? "Signing in" : "Sign in"}
        </button>
      </form>
    </AuthLayout>
  );
}
