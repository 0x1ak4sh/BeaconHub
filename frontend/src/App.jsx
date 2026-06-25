import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
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
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
