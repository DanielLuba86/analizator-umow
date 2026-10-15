// Typy odpowiedzi API z Fazy 5 (backend/app/api/*.py).

export type Role = "asystent" | "prawnik";
export type ContractKind = "najem" | "dostawa" | "zlecenie";
export type ContractSource = "wewnętrzna" | "kontrahent";
export type AnalysisStatus = "queued" | "running" | "done" | "failed" | "quarantined" | "budget_exceeded";
export type FindingType = "strona" | "termin" | "kara" | "ryzyko" | "wstrzyknięcie";
export type RiskLevel = "niskie" | "średnie" | "wysokie";
export type ActionType = "opinia" | "wzorzec" | "eksport" | "kwarantanna";
export type ActionStatus = "oczekuje" | "zatwierdzona" | "odrzucona";

export const CONTRACT_KINDS: ContractKind[] = ["najem", "dostawa", "zlecenie"];
export const CONTRACT_SOURCES: ContractSource[] = ["wewnętrzna", "kontrahent"];
export const FINAL_STATUSES: AnalysisStatus[] = ["done", "failed", "quarantined", "budget_exceeded"];

export type Me = { id: number; login: string; role: Role };

export type ContractListItem = {
  id: number;
  title: string;
  kind: ContractKind;
  source: ContractSource;
  versions: number;
};

export type VersionListItem = { id: number; nr: number; created_at: string };

export type Contract = {
  id: number;
  title: string;
  kind: ContractKind;
  source: ContractSource;
  versions: VersionListItem[];
};

export type ContractCreated = { id: number; version_id: number };
export type VersionCreated = { version_id: number; nr: number };

export type FragmentDto = { id: string; label: string; start: number; end: number };

export type Version = {
  id: number;
  contract_id: number;
  nr: number;
  text: string;
  fragments: FragmentDto[];
};

export type Finding = {
  id: number;
  typ: FindingType;
  teza: string;
  cytat: string;
  fragment_id: string;
  start: number;
  end: number;
  poziom_ryzyka: RiskLevel | null;
  uzasadnienie: string;
  template_id: number | null;
};

export type Analysis = {
  id: number;
  version_id: number;
  status: AnalysisStatus;
  reason: string | null;
  turns: number | null;
  cost_usd: number | null;
  incomplete: boolean;
  official: boolean;
  quarantine: { action_id: number; status: ActionStatus } | null;
  findings: Finding[];
};

export type AnalysisStarted = { analysis_id: number };

export type PendingAction = {
  id: number;
  typ: ActionType;
  analysis_id: number;
  status: ActionStatus;
  payload: Record<string, unknown>;
  created_at: string;
  decided_by: number | null;
  decided_at: string | null;
  export_id: number | null;
};

export type Decision = { id: number; status: ActionStatus; export_id: number | null };

export type FragmentChange = {
  label: string;
  kind: "dodany" | "usunięty" | "zmieniony";
  old_text: string | null;
  new_text: string | null;
};

export type FindingKey = { typ: string; label: string; cytat: string };

export type Comparison = {
  id: number;
  fragment_changes: FragmentChange[];
  finding_changes: { nowe: FindingKey[]; ustąpiło: FindingKey[] } | null;
};
