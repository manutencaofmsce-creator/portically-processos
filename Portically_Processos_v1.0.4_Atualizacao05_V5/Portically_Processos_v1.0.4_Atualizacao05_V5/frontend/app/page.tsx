import LoginPanel from "@/components/LoginPanel";

export default function Home() {
  return (
    <main className="login-shell">
      <section className="brand-panel">
        <header className="brand-header">
          <div className="brand-mark">P</div>
          <div>
            <div className="brand-name">PORTICALLY PROCESSOS</div>
            <div className="brand-subtitle">Módulo do PORTICALLY HUB</div>
          </div>
        </header>

        <section className="hero">
          <div className="restricted-badge">
            <span className="status-dot" />
            AMBIENTE RESTRITO
          </div>

          <h1>
            Controle processual com segurança, rastreabilidade e auditoria.
          </h1>

          <p>
            Acesso privado para consulta, sincronização e organização de processos,
            movimentações e documentos oficiais. Nenhum conteúdo processual é
            exibido antes da autenticação.
          </p>

          <div className="feature-grid">
            <article>
              <strong>Fontes oficiais</strong>
              <span>Estrutura preparada para PJe, TJRN e DataJud.</span>
            </article>
            <article>
              <strong>Auditoria completa</strong>
              <span>Eventos, acessos, sincronizações e integridade registrados.</span>
            </article>
            <article>
              <strong>Documentos protegidos</strong>
              <span>Inventário, controle de acesso e hash SHA-256.</span>
            </article>
          </div>
        </section>

        <footer className="version-footer">
          <span>PORTICALLY HUB</span>
          <span>v1.0.4 · Atualização 05</span>
        </footer>
      </section>

      <LoginPanel />
    </main>
  );
}
