import React, { lazy, Suspense } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import ScrollToTop from './components/ScrollToTop'

const Home = lazy(() => import('./pages/Home/Home'))
const CouplesCounseling = lazy(() => import('./pages/Services/Couples/CouplesCounseling'))
const ParentingGuidance = lazy(() => import('./pages/Services/Parenting/ParentingGuidance'))
const MediationPage = lazy(() => import('./pages/Services/Mediation/MediationPage'))
const GiftedParentingPage = lazy(() => import('./pages/Services/Gifted/GiftedParentingPage'))
const AliyahFamiliesPage = lazy(() => import('./pages/Services/Aliyah/AliyahFamiliesPage'))
const BlogList = lazy(() => import('./pages/Blog/BlogList'))
const BlogPost = lazy(() => import('./pages/Blog/BlogPost'))
const FAQ = lazy(() => import('./pages/FAQ/FAQ'))
const AboutPage = lazy(() => import('./pages/About/AboutPage'))
const ContactPage = lazy(() => import('./pages/Contact/ContactPage'))
const AccessibilityPage = lazy(() => import('./pages/Legal/AccessibilityPage'))
const PrivacyPolicy = lazy(() => import('./pages/Legal/PrivacyPolicy'))
const TermsOfUse = lazy(() => import('./pages/Legal/TermsOfUse'))
const NotFound = lazy(() => import('./pages/NotFound/NotFound'))

function App() {
  return (
    <Router>
      <ScrollToTop />
      <Layout>
        <Suspense fallback={<div className="route-loading" role="status">טוענת...</div>}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/services/couples" element={<CouplesCounseling />} />
            <Route path="/services/parenting" element={<ParentingGuidance />} />
            <Route path="/services/mediation" element={<MediationPage />} />
            <Route path="/services/gifted-parenting" element={<GiftedParentingPage />} />
            <Route path="/services/aliyah-families" element={<AliyahFamiliesPage />} />
            <Route path="/blog" element={<BlogList />} />
            <Route path="/blog/:id" element={<BlogPost />} />
            <Route path="/faq" element={<FAQ />} />
            <Route path="/contact" element={<ContactPage />} />
            <Route path="/accessibility" element={<AccessibilityPage />} />
            <Route path="/privacy" element={<PrivacyPolicy />} />
            <Route path="/terms" element={<TermsOfUse />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </Layout>
    </Router>
  )
}

export default App
