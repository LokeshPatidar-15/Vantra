import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { signup } from "../api";
import AuthLayout from "../components/AuthLayout";
import Field from "../components/Field";
import { ArrowRightIcon, LockIcon, MailIcon } from "../components/icons";

export default function SignupPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault(); // stop the browser's default page reload
    setError("");

    // Client-side checks are only for quick feedback; the backend validates again.
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const cleanEmail = email.trim().toLowerCase();
      await signup(cleanEmail, password);
      navigate("/login", { state: { justSignedUp: true, email: cleanEmail } });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout title="Create your account" subtitle="Start testing and validating your strategies.">
      {error && <div className="alert alert-error">{error}</div>}

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
          autoComplete="new-password"
          placeholder="At least 8 characters"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <Field
          id="confirmPassword"
          label="Confirm password"
          icon={<LockIcon />}
          type="password"
          autoComplete="new-password"
          placeholder="Re-enter your password"
          required
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
        />

        <button className="btn-primary" type="submit" disabled={loading}>
          {loading ? (
            "Creating account..."
          ) : (
            <>
              Sign up <ArrowRightIcon size={16} />
            </>
          )}
        </button>
      </form>

      <p className="auth-footer">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </AuthLayout>
  );
}
