import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ErrorState } from "../../components/ui/Feedback";
import { authService } from "./authService";
import AuthLayout from "./AuthLayout";
import { useAuth } from "./useAuth";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function handleChange(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const payload = await authService.register({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
      });
      register(payload);
      navigate("/dashboard", { replace: true });
    } catch (requestError) {
      setError(requestError.message || "Unable to create the account.");
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
          <Link to="/login">Sign in instead</Link>
        </>
      }
      title="Create your learner profile."
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <label className="auth-field">
          <span>Full name</span>
          <input
            autoComplete="name"
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
            autoComplete="new-password"
            minLength={10}
            name="password"
            onChange={handleChange}
            placeholder="At least 10 characters"
            required
            type="password"
            value={form.password}
          />
        </label>
        {error ? <ErrorState message={error} /> : null}
        <button className="button button-primary auth-submit" disabled={submitting} type="submit">
          {submitting ? "Creating account" : "Create account"}
        </button>
      </form>
    </AuthLayout>
  );
}
