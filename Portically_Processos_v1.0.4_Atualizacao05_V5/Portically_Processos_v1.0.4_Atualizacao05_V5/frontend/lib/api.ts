const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export type ApiMessage = {
  message: string;
};

export type PilotProcess = {
  cnj: string;
  status: "EM_VALIDACAO";
  sync_state: "AGUARDANDO_VALIDACAO_HUMANA";
  official_sync: boolean;
  integrity_state: string;
  related_processes_state: string;
  source_policy: string;
  tabs: string[];
  notice: string;
};

async function parseResponse<T>(response: Response): Promise<T> {
  const data = (await response.json().catch(() => ({}))) as Record<string, unknown>;

  if (!response.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : "Não foi possível concluir a solicitação.";
    throw new Error(detail);
  }

  return data as T;
}

export async function requestOtp(email: string): Promise<ApiMessage> {
  const response = await fetch(`${API_BASE}/api/auth/request-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email })
  });

  return parseResponse<ApiMessage>(response);
}

export async function verifyOtp(email: string, code: string): Promise<ApiMessage> {
  const response = await fetch(`${API_BASE}/api/auth/verify-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, code })
  });

  return parseResponse<ApiMessage>(response);
}

export async function getPilotProcess(): Promise<PilotProcess> {
  const response = await fetch(`${API_BASE}/api/processes/pilot`, {
    method: "GET",
    credentials: "include",
    cache: "no-store"
  });
  return parseResponse<PilotProcess>(response);
}

export async function logout(): Promise<ApiMessage> {
  const response = await fetch(`${API_BASE}/api/auth/logout`, {
    method: "POST",
    credentials: "include"
  });
  return parseResponse<ApiMessage>(response);
}
