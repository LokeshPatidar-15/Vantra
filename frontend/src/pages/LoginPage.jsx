import { useState } from "react";
import { Link, useLocation } from "react-router-dom";

import AuthLayout from "../components/AuthLayout";
import Field from "../components/Field";
import { ArrowRightIcon, LockIcon, MailIcon } from "../components/icons";
import { useAuthStore } from "../store/authStore";

export default function LoginPage() {
  const location = useLocation();
  const justSignedUp = Boolean(location.state?.justSignedUp);
  const login = useAuthStore((state) => state.login);

  const [email, setEmail] = useState(location.state?.email ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
      // On success the store becomes "authenticated" and PublicOnlyRoute redirects us.
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout title="Welcome back" subtitle="Log in to continue.">
      {justSignedUp && !error && <div className="alert alert-success">Account created. Please log in.</div>}
      {error && <div className="alert alert-error">{error}</div>}
      {info && <div className="alert alert-info">{info}</div>}

      <form onSubmit={handleSubmit}>
        <Field
          id="email"
          label="Email"
          icon={<MailIcon />}
          type="email"
          autoComplete="email"
          placeholder="Enter your email address"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <Field
          id="password"
          label="Password"
          icon={<LockIcon />}
          type="password"
          autoComplete="current-password"
          placeholder="Enter your password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <div className="field-row">
          <button type="button" className="link-button" onClick={() => setInfo("Password reset is coming soon.")}>
            Forgot password?
          </button>
        </div>

        <button className="btn-primary" type="submit" disabled={loading}>
          {loading ? (
            "Logging in..."
          ) : (
            <>
              Log in <ArrowRightIcon size={16} />
            </>
          )}
        </button>
      </form>

      <p className="auth-footer">
        New to Vantra? <Link to="/signup">Create an account</Link>
      </p>
    </AuthLayout>
  );
}
