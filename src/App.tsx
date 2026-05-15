import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import ScrollToTop from './components/ScrollToTop'
import Home from './pages/Home/Home'
import CouplesCounseling from './pages/Services/Couples/CouplesCounseling'
import ParentingGuidance from './pages/Services/Parenting/ParentingGuidance'
import Mediation from './pages/Services/Mediation/Mediation'

function App() {
  return (
    <Router>
      <ScrollToTop />
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/services/couples" element={<CouplesCounseling />} />
          <Route path="/services/parenting" element={<ParentingGuidance />} />
          <Route path="/services/mediation" element={<Mediation />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
