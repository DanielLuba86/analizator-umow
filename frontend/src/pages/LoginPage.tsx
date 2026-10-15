import { useState, type FormEvent } from "react";

import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { currentPath, navigate } from "../router";

export function LoginPage() {
  const { login } = useAuth();
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(name, password);
      // Po wygaśnięciu sesji zostajemy na stronie, z której przyszedł użytkownik.
      if (["/", "/login"].includes(currentPath())) navigate("/contracts");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="login">
      <h2>Logowanie</h2>
      <form onSubmit={onSubmit}>
        <label>
          Login
          <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="username" required />
        </label>
        <label>
          Hasło
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <button type="submit" disabled={busy}>
          Zaloguj
        </button>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  );
}
