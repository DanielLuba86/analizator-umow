import { AuthProvider, useAuth } from "./auth/AuthContext";
import { AnalysisRedirect } from "./pages/AnalysisRedirect";
import { ApprovalsPage } from "./pages/ApprovalsPage";
import { ComparePage } from "./pages/ComparePage";
import { ContractPage } from "./pages/ContractPage";
import { ContractsPage } from "./pages/ContractsPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { matchRoute, navigate, useRoute } from "./router";

function Page({ path, isLawyer }: { path: string; isLawyer: boolean }) {
  let m: Record<string, number> | null;
  if ((m = matchRoute("/contracts/:id/compare", path))) return <ComparePage contractId={m.id} />;
  if ((m = matchRoute("/contracts/:id/versions/:vid/analyses/:aid", path)))
    return <ContractPage key={path} contractId={m.id} versionId={m.vid} analysisId={m.aid} />;
  if ((m = matchRoute("/contracts/:id/versions/:vid", path)))
    return <ContractPage key={path} contractId={m.id} versionId={m.vid} />;
  if ((m = matchRoute("/contracts/:id", path))) return <ContractPage key={path} contractId={m.id} />;
  if ((m = matchRoute("/analyses/:id", path))) return <AnalysisRedirect analysisId={m.id} />;
  if (path === "/approvals") {
    return isLawyer ? <ApprovalsPage /> : <p role="alert">Kolejka wniosków jest dostępna tylko dla prawnika.</p>;
  }
  // "/login" zostaje w adresie po wylogowaniu i ponownym zalogowaniu.
  if (["/", "/contracts", "/login"].includes(path)) return <ContractsPage />;
  return <NotFoundPage />;
}

function Brand() {
  return (
    <a className="brand" href="#/contracts">
      <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
        <rect x="1" y="1" width="30" height="30" rx="7" />
        <text x="16" y="23" textAnchor="middle">
          §
        </text>
      </svg>
      <h1>Analizator umów</h1>
    </a>
  );
}

function NavLink({ href, current, children }: { href: string; current: boolean; children: string }) {
  return (
    <a href={href} aria-current={current ? "page" : undefined}>
      {children}
    </a>
  );
}

function Shell() {
  const { user, loading, logout } = useAuth();
  const path = useRoute();
  const isLawyer = user?.role === "prawnik";

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <Brand />
          {user && (
            <>
              <nav aria-label="Główna">
                <NavLink href="#/contracts" current={path !== "/approvals"}>
                  Umowy
                </NavLink>
                {isLawyer && (
                  <NavLink href="#/approvals" current={path === "/approvals"}>
                    Wnioski do zatwierdzenia
                  </NavLink>
                )}
              </nav>
              <span className="user">
                <span className="user-badge">
                  {user.login} <span className="user-role">({user.role})</span>
                </span>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    void logout().finally(() => navigate("/login"));
                  }}
                >
                  Wyloguj
                </button>
              </span>
            </>
          )}
        </div>
      </header>
      <main className={user ? undefined : "auth"}>
        {loading ? <p>Ładowanie…</p> : user ? <Page path={path} isLawyer={isLawyer} /> : <LoginPage />}
      </main>
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
