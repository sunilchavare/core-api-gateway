import { useEffect, useState } from 'react'

function describeError(data, status) {
  if (data && typeof data.detail === 'string') {
    return data.detail
  }

  // FastAPI validation errors (422) come back as a list of problems.
  if (data && Array.isArray(data.detail)) {
    return data.detail
      .map((item) => `${(item.loc ?? []).slice(1).join('.')}: ${item.msg}`)
      .join('; ')
  }

  return `Request failed (HTTP ${status})`
}

async function callApi(apiBase, path, { method = 'GET', token, body } = {}) {
  const headers = {}

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${apiBase}${path}`, {
    method,
    headers,
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  })

  const text = await res.text()

  try {
    return { ok: res.ok, status: res.status, data: text ? JSON.parse(text) : null }
  } catch {
    // Not JSON (for example a plain-text 500 page): report the status only.
    return { ok: res.ok, status: res.status, data: null }
  }
}

const NETWORK_ERROR = 'Cannot reach the gateway. Check that it is running and CORS allows this page.'

function Account({ apiBase, session, setSession, onUseKey }) {
  const [mode, setMode] = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)
  // null means the list has not loaded yet.
  const [keys, setKeys] = useState(null)
  const [reloadCount, setReloadCount] = useState(0)
  const [newKey, setNewKey] = useState(null)
  const [copied, setCopied] = useState(false)
  const [revealed, setRevealed] = useState(false)

  const token = session?.token

  // Load the signed-in user's keys. Reruns after a key is created or revoked.
  useEffect(() => {
    if (!token) {
      return undefined
    }

    let cancelled = false

    callApi(apiBase, '/api/v1/keys', { token })
      .then((result) => {
        if (cancelled) {
          return
        }

        if (result.ok) {
          setKeys(result.data)
        } else if (result.status === 401) {
          setSession(null)
          setNotice({ type: 'error', text: 'Your session expired. Log in again.' })
        } else {
          setNotice({ type: 'error', text: describeError(result.data, result.status) })
        }
      })
      .catch(() => {
        if (!cancelled) {
          setNotice({ type: 'error', text: NETWORK_ERROR })
        }
      })

    return () => {
      cancelled = true
    }
  }, [apiBase, token, reloadCount, setSession])

  function reloadKeys() {
    setReloadCount((count) => count + 1)
  }

  function switchMode(nextMode) {
    setMode(nextMode)
    setNotice(null)
  }

  async function handleAuth(event) {
    event.preventDefault()
    setBusy(true)
    setNotice(null)

    try {
      const path = mode === 'register' ? '/api/v1/auth/register' : '/api/v1/auth/login'
      const result = await callApi(apiBase, path, {
        method: 'POST',
        body: { username, password },
      })

      if (!result.ok) {
        setNotice({ type: 'error', text: describeError(result.data, result.status) })
        return
      }

      setPassword('')

      if (mode === 'register') {
        setMode('login')
        setNotice({ type: 'success', text: 'Account created. Log in to continue.' })
      } else {
        setSession({ token: result.data.access_token, username: result.data.username })
        setKeys(null)
        setNewKey(null)
      }
    } catch {
      setNotice({ type: 'error', text: NETWORK_ERROR })
    } finally {
      setBusy(false)
    }
  }

  async function handleGenerate() {
    setBusy(true)
    setNotice(null)
    setCopied(false)
    setRevealed(false)

    try {
      const result = await callApi(apiBase, '/api/v1/keys/generate', {
        method: 'POST',
        token,
      })

      if (result.ok) {
        setNewKey(result.data.api_key)
        onUseKey(result.data.api_key)
        reloadKeys()
      } else if (result.status === 401) {
        setSession(null)
        setNotice({ type: 'error', text: 'Your session expired. Log in again.' })
      } else {
        setNotice({ type: 'error', text: describeError(result.data, result.status) })
      }
    } catch {
      setNotice({ type: 'error', text: NETWORK_ERROR })
    } finally {
      setBusy(false)
    }
  }

  async function handleRevoke(id) {
    setBusy(true)
    setNotice(null)

    try {
      const result = await callApi(apiBase, `/api/v1/keys/${id}`, {
        method: 'DELETE',
        token,
      })

      if (result.ok) {
        reloadKeys()
      } else if (result.status === 401) {
        setSession(null)
        setNotice({ type: 'error', text: 'Your session expired. Log in again.' })
      } else {
        setNotice({ type: 'error', text: describeError(result.data, result.status) })
      }
    } catch {
      setNotice({ type: 'error', text: NETWORK_ERROR })
    } finally {
      setBusy(false)
    }
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(newKey)
      setCopied(true)
    } catch {
      setNotice({ type: 'error', text: 'Could not copy. Select the key and copy it manually.' })
    }
  }

  function handleLogout() {
    setSession(null)
    setKeys(null)
    setNewKey(null)
    setNotice(null)
  }

  const noticeBlock = notice && (
    <div
      className={`notice ${notice.type}`}
      role={notice.type === 'error' ? 'alert' : 'status'}
    >
      {notice.text}
    </div>
  )

  if (!session) {
    return (
      <section className="panel account-panel" id="account">
        <div className="panel-heading">
          <div>
            <h2>{mode === 'login' ? 'Log in' : 'Create an account'}</h2>
            <p>
              {mode === 'login'
                ? 'Log in to generate and manage API keys.'
                : 'Usernames are 3 to 50 characters. Passwords are at least 8 characters.'}
            </p>
          </div>
          <div className="auth-tabs" role="group" aria-label="Account action">
            <button
              type="button"
              className={mode === 'login' ? 'active' : ''}
              aria-pressed={mode === 'login'}
              onClick={() => switchMode('login')}
            >
              Log in
            </button>
            <button
              type="button"
              className={mode === 'register' ? 'active' : ''}
              aria-pressed={mode === 'register'}
              onClick={() => switchMode('register')}
            >
              Register
            </button>
          </div>
        </div>

        {noticeBlock}

        <form className="account-form" onSubmit={handleAuth}>
          <label className="field-label" htmlFor="auth-username">Username</label>
          <input
            id="auth-username"
            className="full-input"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
          />

          <label className="field-label" htmlFor="auth-password">Password</label>
          <input
            id="auth-password"
            className="full-input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            required
          />

          <button className="primary-button" type="submit" disabled={busy}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
          </button>
        </form>

        <p className="field-help">
          Your login token is held in this page's memory only. Refreshing the page logs you out.
        </p>
      </section>
    )
  }

  return (
    <section className="panel account-panel" id="account">
      <div className="panel-heading">
        <div>
          <h2>Signed in as {session.username}</h2>
          <p>Generate API keys and revoke the ones you no longer need.</p>
        </div>
        <button className="secondary-button" type="button" onClick={handleLogout}>
          Log out
        </button>
      </div>

      {noticeBlock}

      <div className="key-actions">
        <button className="primary-button" type="button" onClick={handleGenerate} disabled={busy}>
          Generate API key
        </button>
        <span className="field-help">Up to 5 active keys per account.</span>
      </div>

      {newKey && (
        <div className="key-reveal" role="status">
          <strong>Your new API key</strong>
          <p>Copy it now. It can't be shown again after you leave this screen, and the gateway stores only a hash.</p>
          <code className={revealed ? '' : 'masked'} aria-label={revealed ? 'API key' : 'API key hidden'}>
            {revealed ? newKey : '•'.repeat(32)}
          </code>
          <div className="key-reveal-actions">
            <button className="secondary-button" type="button" onClick={handleCopy}>
              {copied ? 'Copied ✓' : 'Copy key'}
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => setRevealed((value) => !value)}
              aria-pressed={revealed}
            >
              {revealed ? 'Hide key' : 'Show key'}
            </button>
            <span className="field-help">It was also loaded into the request builder.</span>
          </div>
        </div>
      )}

      <h3 className="section-title">Your keys</h3>

      {keys === null ? (
        <div className="empty-history">Loading keys…</div>
      ) : keys.length === 0 ? (
        <div className="empty-history">No keys yet. Generate your first one above.</div>
      ) : (
        <div className="keys-list">
          {keys.map((key) => (
            <div className="key-row" key={key.id}>
              <span className="key-id">#{key.id}</span>
              <span className={`http-status ${key.is_active ? 'success' : 'failure'}`}>
                {key.is_active ? 'Active' : 'Revoked'}
              </span>
              <span className="duration">{key.quota_limit} requests / min</span>
              <span className="history-time">{new Date(key.created_at).toLocaleString()}</span>
              <button
                className="secondary-button"
                type="button"
                onClick={() => handleRevoke(key.id)}
                disabled={!key.is_active || busy}
              >
                Revoke
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export default Account
