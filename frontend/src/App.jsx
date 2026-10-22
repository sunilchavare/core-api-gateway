import './App.css'

function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">G</div>
          <div>
            <h2>Core Gateway</h2>
            <span>API MANAGEMENT</span>
          </div>
        </div>

        <nav>
          <p className="nav-label">WORKSPACE</p>
          <a className="nav-item active" href="#dashboard">▦ Dashboard</a>
          <a className="nav-item" href="#api-keys">⌘ API Keys</a>
          <a className="nav-item" href="#proxy">⇄ Proxy Tester</a>
          <a className="nav-item" href="#settings">⚙ Settings</a>
        </nav>

        <div className="sidebar-bottom">
          <div className="avatar">D</div>
          <div>
            <strong>Developer</strong>
            <span>API Administrator</span>
          </div>
        </div>
      </aside>

      <main className="main-content" id="dashboard">
        <header className="topbar">
          <div>
            <p className="breadcrumb">Workspace / Overview</p>
            <h1>Dashboard</h1>
          </div>
          <div className="connection-status">
            <span className="status-dot" />
            Gateway interface
          </div>
        </header>

        <section className="welcome">
          <div>
            <p className="eyebrow">CORE API GATEWAY</p>
            <h2>Your APIs, one gateway.</h2>
            <p>Manage access, monitor requests, and test your services.</p>
          </div>
          <div className="welcome-icon">⌘</div>
        </section>

        <section className="section">
          <div className="section-heading">
            <div>
              <h2>System overview</h2>
              <p>Your gateway at a glance</p>
            </div>
          </div>

          <div className="stats-grid">
            <article className="stat-card">
              <div className="stat-top">
                <span>Gateway status</span>
                <span className="stat-icon purple">↗</span>
              </div>
              <h3>Checking soon</h3>
              <p className="stat-note">Backend connection not yet wired</p>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span>Authentication</span>
                <span className="stat-icon blue">⌑</span>
              </div>
              <h3>JWT + API Keys</h3>
              <p className="stat-note">Protected API access</p>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span>Rate limiting</span>
                <span className="stat-icon green">◷</span>
              </div>
              <h3>10 requests</h3>
              <p className="stat-note">Per key, per 60-second window</p>
            </article>
          </div>
        </section>

        <section className="section tools-section">
          <div className="section-heading">
            <div>
              <h2>Developer tools</h2>
              <p>Quick access to your gateway features</p>
            </div>
          </div>

          <div className="tools-grid">
            <article className="tool-card" id="api-keys">
              <div className="tool-icon purple">⌘</div>
              <h3>API key management</h3>
              <p>Generate and manage keys used to authenticate requests.</p>
              <button onClick={() => alert('API key management is coming next.')}>
                Manage keys <span>→</span>
              </button>
            </article>

            <article className="tool-card" id="proxy">
              <div className="tool-icon blue">⇄</div>
              <h3>Proxy tester</h3>
              <p>Send a request through the gateway to your downstream service.</p>
              <button onClick={() => alert('Proxy tester is coming next.')}>
                Test proxy <span>→</span>
              </button>
            </article>
          </div>
        </section>

        <footer>
          <span>Core API Gateway</span>
          <span>Development environment</span>
        </footer>
      </main>
    </div>
  )
}

export default App