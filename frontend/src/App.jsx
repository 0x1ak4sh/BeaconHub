import React from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AccessPoints from './pages/AccessPoints'
import APDetail from './pages/APDetail'
import Adapters from './pages/Adapters'
import Clients from './pages/Clients'
import ClientDetail from './pages/ClientDetail'
import Attacks from './pages/Attacks'
import Scenarios from './pages/Scenarios'
import Logs from './pages/Logs'

function NotFound() {
  return (
    <div className="card">
      <div className="empty-state">
        <span className="material-symbols-outlined" style={{ fontSize: 64, color: 'var(--text-muted)' }}>error_outline</span>
        <div className="font-semibold text-on-surface" style={{ fontSize: 20 }}>404 — Page Not Found</div>
        <div className="text-sm text-on-surface-variant">
          The page you're looking for doesn't exist.
        </div>
        <Link to="/" className="btn btn-primary mt-2">
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>home</span>
          Back to Dashboard
        </Link>
      </div>
    </div>
  )
}

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/access-points" element={<AccessPoints />} />
          <Route path="/access-points/:apId" element={<APDetail />} />
          <Route path="/adapters" element={<Adapters />} />
          <Route path="/clients" element={<Clients />} />
          <Route path="/clients/:clientId" element={<ClientDetail />} />
          <Route path="/attacks" element={<Attacks />} />
          <Route path="/scenarios" element={<Scenarios />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
