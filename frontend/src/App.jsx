import { useEffect, useState } from 'react'
import './App.css'

// Override with VITE_API_BASE in frontend/.env.local (see .env.example).
const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'
const HISTORY_LIMIT = 8
const BODY_METHODS = ['POST', 'PUT', 'PATCH']

const VIEWS = {
  request: {
    label: 'Request builder',
    breadcrumb: 'Workspace / HTTP client',
    description: 'Send requests through your API gateway and inspect the response.',
  },
  history: {
    label: 'Request history',
    breadcrumb: 'Workspace / History',
    description: 'Re-run recent requests from this browser session.',
  },
  inspector: {
    label: 'Response inspector',
    breadcrumb: 'Workspace / Response',
    description: 'Read the full body and timing of the latest response.',
  },
}

function isSuccess(status) {
  return typeof status === 'number' && status < 400
}

// Returns the label to show in the sidebar. Never throws and never sets state.
async function fetchHealth() {
  const start = performance.now()
  let label

  try {
    const res = await fetch(`${API_BASE}/health`)
    label = res.ok ? 'Online' : `HTTP ${res.status}`
  } catch {
    label = 'Unreachable'
  }

  // Keep the "Checking…" state visible long enough to be noticed.
  const remaining = Math.max(0, 400 - (performance.now() - start))
  await new Promise((resolve) => setTimeout(resolve, remaining))

  return label
}

function App() {
  const [method, setMethod] = useState('GET')
  const [endpoint, setEndpoint] = useState('/api/v1/proxy/hello/hello')
  const [apiKey, setApiKey] = useState('')
  const [requestBody, setRequestBody] = useState('{\n  \n}')
  const [status, setStatus] = useState(null)
  const [duration, setDuration] = useState(null)
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(false)
  const [health, setHealth] = useState('Unknown')
  // Starts true because the first check runs as soon as the page mounts.
  const [checkingHealth, setCheckingHealth] = useState(true)
  const [history, setHistory] = useState([])
  const [activeView, setActiveView] = useState('request')

  useEffect(() => {
    let cancelled = false

    fetchHealth().then((label) => {
      if (!cancelled) {
        setHealth(label)
        setCheckingHealth(false)
      }
    })

    // Ignore the result if the component unmounts before the check finishes.
    return () => {
      cancelled = true
    }
  }, [])

  function handleCheckConnection() {
    setCheckingHealth(true)
    fetchHealth().then((label) => {
      setHealth(label)
      setCheckingHealth(false)
    })
  }

  function addToHistory(entry) {
    setHistory((items) => [entry, ...items].slice(0, HISTORY_LIMIT))
  }

  async function sendRequest() {
    if (!endpoint.trim() || !endpoint.startsWith('/')) {
      setStatus('Invalid URL')
      setResponse('Enter an endpoint starting with /.')
      return
    }

    const hasBody = BODY_METHODS.includes(method)

    if (hasBody) {
      try {
        JSON.parse(requestBody)
      } catch {
        setStatus('Invalid JSON')
        setResponse('Fix the JSON request body before sending.')
        return
      }
    }

    setLoading(true)
    setResponse(null)
    setStatus(null)
    setDuration(null)

    const start = performance.now()
    const entry = {
      method,
      endpoint,
      requestBody: hasBody ? requestBody : undefined,
      time: new Date().toLocaleTimeString(),
    }

    try {
      const headers = {}

      if (apiKey.trim()) {
        headers['X-API-Key'] = apiKey.trim()
      }

      if (hasBody) {
        headers['Content-Type'] = 'application/json'
      }

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method,
        headers,
        ...(hasBody ? { body: requestBody } : {}),
      })

      const elapsed = Math.round(performance.now() - start)
      const text = await res.text()
      let body

      try {
        body = JSON.stringify(JSON.parse(text), null, 2)
      } catch {
        body = text
      }

      setStatus(res.status)
      setDuration(elapsed)
      setResponse(body === '' ? '(empty response body)' : body)
      addToHistory({ ...entry, status: res.status, duration: elapsed })
    } catch (error) {
      const elapsed = Math.round(performance.now() - start)

      setStatus('Network error')
      setDuration(elapsed)
      setResponse(
        `${error.message}\n\nCheck that the FastAPI gateway is running at ${API_BASE} and CORS is configured.`,
      )
      addToHistory({ ...entry, status: 'ERR', duration: elapsed })
    } finally {
      setLoading(false)
    }
  }

  function loadFromHistory(item) {
    setMethod(item.method)
    setEndpoint(item.endpoint)

    if (item.requestBody !== undefined) {
      setRequestBody(item.requestBody)
    }

    setActiveView('request')
  }

  const view = VIEWS[activeView]

  return (
    <div className="workspace">
      <aside className="sidebar">
        <a className="brand" href="#workspace">
          <span className="brand-mark">CG</span>
          <span>
            <strong>Core Gateway</strong>
            <small>API WORKSPACE</small>
          </span>
        </a>

        <nav aria-label="Workspace views">
          <div className="nav-caption">WORKSPACE</div>

          {Object.entries(VIEWS).map(([key, item]) => (
            <button
              key={key}
              type="button"
              className={`nav-link ${activeView === key ? 'active' : ''}`}
              aria-current={activeView === key ? 'page' : undefined}
              onClick={() => setActiveView(key)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="nav-caption">LOCAL ENVIRONMENT</div>
          <div className="environment">
            <span className={`dot ${health === 'Online' ? 'online' : ''}`} />
            <span>Gateway</span>
            <span className="environment-value">{health}</span>
          </div>
          <button
            className="text-button"
            onClick={handleCheckConnection}
            type="button"
            disabled={checkingHealth}
          >
            {checkingHealth ? 'Checking…' : 'Check connection ↗'}
          </button>
        </div>
      </aside>

      <main className="main-panel" id="workspace">
        <header className="page-header">
          <div>
            <div className="breadcrumb">{view.breadcrumb}</div>
            <h1>{view.label}</h1>
            <p>{view.description}</p>
          </div>
          <span className="local-label">LOCAL DEVELOPMENT</span>
        </header>

        {activeView === 'request' && (
          <section className="panel request-panel" id="request">
            <div className="panel-heading">
              <div>
                <h2>New request</h2>
                <p>Configure an endpoint and send a request.</p>
              </div>
              <span className="request-type">HTTP</span>
            </div>

            <form
              onSubmit={(event) => {
                event.preventDefault()
                sendRequest()
              }}
            >
              <label className="field-label" htmlFor="endpoint">Request URL</label>

              <div className="request-line">
                <select
                  aria-label="HTTP method"
                  value={method}
                  onChange={(event) => setMethod(event.target.value)}
                >
                  <option>GET</option>
                  <option>POST</option>
                  <option>PUT</option>
                  <option>PATCH</option>
                  <option>DELETE</option>
                </select>

                <input
                  id="endpoint"
                  value={endpoint}
                  onChange={(event) => setEndpoint(event.target.value)}
                  placeholder="/api/v1/proxy/hello/hello"
                  required
                />

                <button className="send-button" type="submit" disabled={loading}>
                  {loading ? 'Sending…' : 'Send request'}
                </button>
              </div>

              <label className="field-label" htmlFor="api-key">API key</label>
              <input
                id="api-key"
                className="full-input"
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder="Enter your API key"
                autoComplete="off"
                aria-describedby="api-key-help"
              />

              <p className="field-help" id="api-key-help">
                Sent in the X-API-Key header. The key stays in this page's memory only.
              </p>

              {BODY_METHODS.includes(method) && (
                <div className="body-editor">
                  <label className="field-label" htmlFor="request-body">
                    Request body · JSON
                  </label>
                  <textarea
                    id="request-body"
                    value={requestBody}
                    onChange={(event) => setRequestBody(event.target.value)}
                    placeholder={'{\n  "key": "value"\n}'}
                    spellCheck={false}
                    rows={8}
                  />
                </div>
              )}
            </form>

            {status !== null && (
              <div className="request-result">
                <div className="request-result-heading">
                  <strong>Latest result</strong>
                  <span className={`http-status ${isSuccess(status) ? 'success' : 'failure'}`}>
                    {typeof status === 'number' ? `HTTP ${status}` : status}
                  </span>
                  {duration !== null && (
                    <span className="duration">{duration} ms</span>
                  )}
                </div>

                <pre className="request-result-body">
                  {response ?? 'Waiting for response…'}
                </pre>

                <button
                  type="button"
                  className="text-button"
                  onClick={() => setActiveView('inspector')}
                >
                  Open full response inspector →
                </button>
              </div>
            )}
          </section>
        )}

        {activeView === 'inspector' && (
          <section className="panel response-panel" id="response">
            <div className="panel-heading response-heading">
              <div>
                <h2>Response</h2>
                <p>Server response body and request timing.</p>
              </div>
              <div className="response-meta">
                {status !== null && (
                  <span className={`http-status ${isSuccess(status) ? 'success' : 'failure'}`}>
                    {typeof status === 'number' ? `HTTP ${status}` : status}
                  </span>
                )}
                {duration !== null && <span className="duration">{duration} ms</span>}
              </div>
            </div>

            <div className="response-toolbar">
              <span>Response body</span>
              <span>JSON / text</span>
            </div>

            <pre className="response-body" aria-live="polite">
              {response ?? 'Send a request to view the response here.'}
            </pre>
          </section>
        )}

        {activeView === 'history' && (
          <section className="panel history-panel" id="history">
            <div className="panel-heading">
              <div>
                <h2>Recent requests</h2>
                <p>Requests made during this browser session. API keys are never saved.</p>
              </div>

              <div className="history-actions">
                <span className="history-count">{history.length} / {HISTORY_LIMIT}</span>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setHistory([])}
                  disabled={history.length === 0}
                >
                  Clear history
                </button>
              </div>
            </div>

            {history.length === 0 ? (
              <div className="empty-history">
                No requests yet. Send your first request from the request builder.
              </div>
            ) : (
              <div className="history-list">
                {history.map((item, index) => (
                  <button
                    className="history-row"
                    key={`${item.time}-${index}`}
                    type="button"
                    onClick={() => loadFromHistory(item)}
                    title="Load this request into the builder"
                  >
                    <span className={`method-tag ${item.method.toLowerCase()}`}>
                      {item.method}
                    </span>
                    <code>{item.endpoint}</code>
                    <span className={isSuccess(item.status) ? 'history-success' : 'history-failure'}>
                      {item.status}
                    </span>
                    <span className="history-duration">{item.duration} ms</span>
                    <span className="history-time">{item.time}</span>
                  </button>
                ))}
              </div>
            )}
          </section>
        )}

        <footer className="page-footer">
          <span>Core API Gateway</span>
          <span>Request history clears on refresh.</span>
        </footer>
      </main>
    </div>
  )
}

export default App
