"use client";

import { useEffect, useState } from "react";
import { getPilotProcess, logout, PilotProcess } from "@/lib/api";

export default function ProcessosPage() {
  const [data, setData] = useState<PilotProcess | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("Resumo");

  useEffect(() => {
    getPilotProcess()
      .then((result) => setData(result))
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Sessão inválida.");
        window.setTimeout(() => window.location.assign("/"), 900);
      });
  }, []);

  async function handleLogout() {
    await logout().catch(() => undefined);
    window.location.assign("/");
  }

  if (error) {
    return <main className="workspace-loading">{error}</main>;
  }

  if (!data) {
    return <main className="workspace-loading">Validando sessão segura...</main>;
  }

  return (
    <main className="workspace-shell">
      <aside className="workspace-sidebar">
        <div>
          <div className="workspace-brand">P</div>
          <div className="workspace-title">PORTICALLY PROCESSOS</div>
          <div className="workspace-subtitle">Módulo do PORTICALLY HUB</div>
        </div>

        <nav className="workspace-nav" aria-label="Navegação do processo">
          {data.tabs.map((tab) => (
            <button
              key={tab}
              type="button"
              className={activeTab === tab ? "nav-item active" : "nav-item"}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </nav>

        <button className="logout-button" type="button" onClick={handleLogout}>
          Encerrar sessão
        </button>
      </aside>

      <section className="workspace-content">
        <header className="workspace-header">
          <div>
            <div className="eyebrow">PROCESSO PILOTO · ISOLADO</div>
            <h1>{data.cnj}</h1>
          </div>
          <div className="status-stack">
            <span className="status-pill warning">Em validação</span>
            <span className="status-pill neutral">Sincronização oficial pendente</span>
          </div>
        </header>

        <section className="process-alert">
          <strong>Regra de segurança ativa</strong>
          <p>{data.notice}</p>
        </section>

        {activeTab === "Resumo" ? (
          <section className="process-grid">
            <article className="process-card">
              <span>Sincronização</span>
              <strong>Aguardando validação humana</strong>
              <small>Nenhuma fonte foi marcada como sincronizada.</small>
            </article>
            <article className="process-card">
              <span>Integridade documental</span>
              <strong>Aguardando documentos oficiais</strong>
              <small>Hash e inventário serão gerados somente após captura legítima.</small>
            </article>
            <article className="process-card">
              <span>Processos relacionados</span>
              <strong>Não validado</strong>
              <small>Nenhum vínculo é criado por aproximação de número ou nome.</small>
            </article>
            <article className="process-card">
              <span>Política de fonte</span>
              <strong>Somente fontes oficiais</strong>
              <small>DataJud/CNJ, PJe/tribunais e demais fontes oficiais pertinentes.</small>
            </article>
          </section>
        ) : (
          <section className="empty-state">
            <div className="eyebrow">{activeTab.toUpperCase()}</div>
            <h2>Estrutura protegida e pronta para dados verificados</h2>
            <p>
              Esta seção permanece sem conteúdo processual inventado. Os registros serão exibidos
              somente depois da coleta oficial, validação de identidade do processo e controles de
              auditoria e integridade aplicáveis.
            </p>
          </section>
        )}

        <footer className="workspace-footer">
          <span>PORTICALLY HUB</span>
          <span>v1.0.4 · Atualização 05</span>
        </footer>
      </section>
    </main>
  );
}
