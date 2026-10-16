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

function Shell() {
  const { user, loading, logout } = useAuth();
  const path = useRoute();

  if (loading) return <p>Ładowanie…</p>;
  if (!user) return <LoginPage />;

  const isLawyer = user.role === "prawnik";
  return (
    <>
      <header className="topbar">
        <nav aria-label="Główna">
          <a href="#/contracts">Umowy</a>
          {isLawyer && <a href="#/approvals">Wnioski do zatwierdzenia</a>}
        </nav>
        <span className="user">
          {user.login} ({user.role})
          <button
            type="button"
            onClick={() => {
              void logout().finally(() => navigate("/login"));
            }}
          >
            Wyloguj
          </button>
        </span>
      </header>
      <Page path={path} isLawyer={isLawyer} />
    </>
  );
}

export default function App() {
  return (
    <main>
      <h1>Analizator umów</h1>
      <AuthProvider>
        <Shell />
      </AuthProvider>
    </main>
  );
}
