import { useState, type FormEvent } from "react";

import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { currentPath, navigate } from "../router";
import { useBusy } from "../useBusy";

export function LoginPage() {
  const { login } = useAuth();
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, guard] = useBusy();

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void guard(async () => {
      setError(null);
      try {
        await login(name, password);
        // Po wygaśnięciu sesji zostajemy na stronie, z której przyszedł użytkownik.
        if (["/", "/login"].includes(currentPath())) navigate("/contracts");
      } catch (err) {
        setError(errorMessage(err));
      }
    });
  }

  return (
    <section className="login card">
      <h2>Logowanie</h2>
      <p className="meta">Zaloguj się, aby analizować umowy.</p>
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
        <button type="submit" className="primary" disabled={busy}>
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
