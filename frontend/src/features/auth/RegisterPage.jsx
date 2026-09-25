import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ErrorState } from "../../components/ui/Feedback";
import { AUTH_ROUTES, MAX_EMAIL_LENGTH, MIN_NAME_LENGTH, MIN_PASSWORD_LENGTH, PASSWORD_HINT } from "./authPolicy";
import { authService } from "./authService";
import AuthLayout from "./AuthLayout";
import { useAuth } from "./useAuth";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const EMPTY_FORM = { name: "", email: "", password: "" };

/**
 * Mirror of the backend rules in `backend/app/schemas/auth.py`, so an obvious
 * mistake is caught before a round trip. The API re-validates regardless.
 */
function validate({ name, email, password }) {
  if (!name.trim()) {
    return "Enter your name so we can personalise your workspace.";
  }
  if (!EMAIL_PATTERN.test(email.trim())) {
    return "Enter a valid email address.";
  }
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `Your password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  return "";
}

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function handleChange(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();

    const message = validate(form);
    if (message) {
      setError(message);
      return;
    }

    setError("");
    setSubmitting(true);
    try {
      const payload = await authService.register({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
      });
      register(payload);
      navigate(AUTH_ROUTES.workspace, { replace: true });
    } catch (requestError) {
      setError(requestError?.message || "Unable to create the account.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      description="Create an account to track your progress across sessions and devices."
      eyebrow="Get started"
      footer={
        <>
          <span>Already have an account?</span>
          <Link to={AUTH_ROUTES.login}>Sign in instead</Link>
        </>
      }
      title="Create your learner profile."
    >
      <form className="auth-form" noValidate onSubmit={handleSubmit}>
        <label className="auth-field">
          <span>Full name</span>
          <input
            autoComplete="name"
            autoFocus
            maxLength={120}
            minLength={MIN_NAME_LENGTH}
            name="name"
            onChange={handleChange}
            placeholder="Ada Lovelace"
            required
            type="text"
            value={form.name}
          />
        </label>
        <label className="auth-field">
          <span>Email</span>
          <input
            autoComplete="email"
            maxLength={MAX_EMAIL_LENGTH}
            name="email"
            onChange={handleChange}
            placeholder="you@example.com"
            required
            type="email"
            value={form.email}
          />
        </label>
        <div className="auth-field-group">
          <label className="auth-field">
            <span>Password</span>
            <input
              aria-describedby="register-password-hint"
              autoComplete="new-password"
              minLength={MIN_PASSWORD_LENGTH}
              name="password"
              onChange={handleChange}
              placeholder={PASSWORD_HINT}
              required
              type="password"
              value={form.password}
            />
          </label>
          <small className="auth-hint" id="register-password-hint">
            {PASSWORD_HINT}. Stored hashed, never in plain text.
          </small>
        </div>
        {error ? <ErrorState message={error} /> : null}
        <button className="button button-primary auth-submit" disabled={submitting} type="submit">
          {submitting ? "Creating account" : "Create account"}
        </button>
      </form>
    </AuthLayout>
  );
}
