import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import ScrollToTop from './components/ScrollToTop'
import Home from './pages/Home/Home'
import CouplesCounseling from './pages/Services/Couples/CouplesCounseling'
import ParentingGuidance from './pages/Services/Parenting/ParentingGuidance'
import Mediation from './pages/Services/Mediation/Mediation'
import BlogList from './pages/Blog/BlogList'
import BlogPost from './pages/Blog/BlogPost'
import FAQ from './pages/FAQ/FAQ'
import AboutPage from './pages/About/AboutPage'
import ContactPage from './pages/Contact/ContactPage'
import AccessibilityPage from './pages/Legal/AccessibilityPage'
import PrivacyPolicy from './pages/Legal/PrivacyPolicy'
import TermsOfUse from './pages/Legal/TermsOfUse'

function App() {
  return (
    <Router>
      <ScrollToTop />
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/services/couples" element={<CouplesCounseling />} />
          <Route path="/services/parenting" element={<ParentingGuidance />} />
          <Route path="/services/mediation" element={<Mediation />} />
          <Route path="/blog" element={<BlogList />} />
          <Route path="/blog/:id" element={<BlogPost />} />
          <Route path="/faq" element={<FAQ />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/accessibility" element={<AccessibilityPage />} />
          <Route path="/privacy" element={<PrivacyPolicy />} />
          <Route path="/terms" element={<TermsOfUse />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
