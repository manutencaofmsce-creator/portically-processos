"use client";

import { FormEvent, useState } from "react";
import { requestOtp, verifyOtp } from "@/lib/api";

type Phase = "email" | "otp";

export default function LoginPanel() {
  const [phase, setPhase] = useState<Phase>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [status, setStatus] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleRequestOtp(event: FormEvent) {
    event.preventDefault();
    setStatus(null);

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail || !normalizedEmail.includes("@")) {
      setStatus({ kind: "error", message: "Informe um e-mail válido." });
      return;
    }

    try {
      setLoading(true);
      const result = await requestOtp(normalizedEmail);
      setEmail(normalizedEmail);
      setPhase("otp");
      setStatus({ kind: "success", message: result.message });
    } catch (error) {
      setStatus({
        kind: "error",
        message: error instanceof Error ? error.message : "Falha ao solicitar o código."
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyOtp(event: FormEvent) {
    event.preventDefault();
    setStatus(null);

    if (!/^\d{6}$/.test(code)) {
      setStatus({
        kind: "error",
        message: "Digite o código de 6 dígitos recebido por e-mail."
      });
      return;
    }

    try {
      setLoading(true);
      const result = await verifyOtp(email, code);
      setStatus({ kind: "success", message: result.message });
      window.location.assign("/processos");
    } catch (error) {
      setStatus({
        kind: "error",
        message: error instanceof Error ? error.message : "Código inválido."
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="access-panel" aria-labelledby="access-title">
      <div className="access-card">
        <div className="lock-icon" aria-hidden="true">🔐</div>

        <h2 id="access-title">Acesso ao sistema</h2>
        <p className="access-copy">
          Informe o e-mail autorizado. Um código temporário será enviado para
          confirmar sua identidade.
        </p>

        {phase === "email" ? (
          <form onSubmit={handleRequestOtp}>
            <label htmlFor="email">E-mail</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="Digite seu e-mail"
              disabled={loading}
            />
            <button type="submit" disabled={loading}>
              {loading ? "Enviando..." : "Enviar código de acesso"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyOtp}>
            <div className="authorized-email">
              Código enviado para <strong>{email}</strong>
            </div>
            <label htmlFor="otp">Código de segurança</label>
            <input
              id="otp"
              inputMode="numeric"
              maxLength={6}
              autoComplete="one-time-code"
              value={code}
              onChange={(event) =>
                setCode(event.target.value.replace(/\D/g, "").slice(0, 6))
              }
              placeholder="000000"
              disabled={loading}
            />
            <button type="submit" disabled={loading}>
              {loading ? "Validando..." : "Entrar no Portically Processos"}
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => {
                setPhase("email");
                setCode("");
                setStatus(null);
              }}
              disabled={loading}
            >
              Trocar e-mail
            </button>
          </form>
        )}

        {status && (
          <div
            className={`status-message ${status.kind}`}
            role={status.kind === "error" ? "alert" : "status"}
          >
            {status.message}
          </div>
        )}

        <div className="security-note">
          <strong>Segurança:</strong> o código expira em poucos minutos e deve ser
          utilizado uma única vez. Nenhuma informação processual é liberada antes
          da autenticação válida no servidor.
        </div>
      </div>
    </section>
  );
}
