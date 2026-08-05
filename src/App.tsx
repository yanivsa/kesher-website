import React, { useEffect, useState } from 'react'
import { BrowserRouter as Router, Navigate, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import ScrollToTop from './components/ScrollToTop'

type PageModule = { default: React.ComponentType };

const loadable = (loader: () => Promise<PageModule>) => {
  let Component: React.ComponentType | undefined;
  let pending: Promise<void> | undefined;

  const preload = () => {
    pending ??= loader().then((module) => {
      Component = module.default;
    });
    return pending;
  };

  const LoadablePage = () => {
    const [, refresh] = useState(0);

    useEffect(() => {
      if (Component) return;
      let active = true;
      preload().then(() => {
        if (active) refresh((value) => value + 1);
      });
      return () => {
        active = false;
      };
    }, []);

    if (!Component) {
      return <div className="route-loading" role="status">טוענת...</div>;
    }
    return <Component />;
  };

  return { Page: LoadablePage, preload };
};

const home = loadable(() => import('./pages/Home/Home'));
const beta = loadable(() => import('./pages/Beta/BetaPage'));
const beta2 = loadable(() => import('./pages/Beta/Beta2Page'));
const beta3 = loadable(() => import('./pages/Beta/Beta3Page'));
const couples = loadable(() => import('./pages/Services/Couples/CouplesCounseling'));
const premarital = loadable(() => import('./pages/Services/Premarital/PremaritalFirstYearPage'));
const parenting = loadable(() => import('./pages/Services/Parenting/ParentingGuidance'));
const mediation = loadable(() => import('./pages/Services/Mediation/MediationPage'));
const gifted = loadable(() => import('./pages/Services/Gifted/GiftedParentingPage'));
const aliyah = loadable(() => import('./pages/Services/Aliyah/AliyahFamiliesPage'));
const relocation = loadable(() => import('./pages/Services/Relocation/CouplesAliyahRelocationPage'));
const lateSingleness = loadable(() => import('./pages/Services/Singles/LateSinglenessPage'));
const findingRelationship = loadable(() => import('./pages/Services/Singles/FindingRelationshipPage'));
const blogList = loadable(() => import('./pages/Blog/BlogList'));
const blogPost = loadable(() => import('./pages/Blog/BlogPost'));
const faq = loadable(() => import('./pages/FAQ/FAQ'));
const about = loadable(() => import('./pages/About/AboutPage'));
const contact = loadable(() => import('./pages/Contact/ContactPage'));
const appointment = loadable(() => import('./pages/Appointment/AppointmentPage'));
const accessibility = loadable(() => import('./pages/Legal/AccessibilityPage'));
const privacy = loadable(() => import('./pages/Legal/PrivacyPolicy'));
const terms = loadable(() => import('./pages/Legal/TermsOfUse'));
const couplesCounselingAshdod = loadable(() => import('./pages/Landing/CouplesCounselingAshdod/CouplesCounselingAshdodPage'));
const thankYouBooked = loadable(() => import('./pages/ThankYou/ThankYouBookedPage'));
const thankYouContact = loadable(() => import('./pages/ThankYou/ThankYouContactPage'));
const notFound = loadable(() => import('./pages/NotFound/NotFound'));

const {
  Page: Home,
} = home;
const { Page: Beta } = beta;
const { Page: Beta2 } = beta2;
const { Page: Beta3 } = beta3;
const { Page: CouplesCounseling } = couples;
const { Page: PremaritalPage } = premarital;
const { Page: ParentingGuidance } = parenting;
const { Page: MediationPage } = mediation;
const { Page: GiftedParentingPage } = gifted;
const { Page: AliyahFamiliesPage } = aliyah;
const { Page: RelocationPage } = relocation;
const { Page: LateSinglenessPage } = lateSingleness;
const { Page: FindingRelationshipPage } = findingRelationship;
const { Page: BlogList } = blogList;
const { Page: BlogPost } = blogPost;
const { Page: FAQ } = faq;
const { Page: AboutPage } = about;
const { Page: ContactPage } = contact;
const { Page: AppointmentPage } = appointment;
const { Page: AccessibilityPage } = accessibility;
const { Page: PrivacyPolicy } = privacy;
const { Page: TermsOfUse } = terms;
const { Page: CouplesCounselingAshdodPage } = couplesCounselingAshdod;
const { Page: ThankYouBookedPage } = thankYouBooked;
const { Page: ThankYouContactPage } = thankYouContact;
const { Page: NotFound } = notFound;

const routeLoaders: Array<[RegExp, () => Promise<void>]> = [
  [/^\/$/, home.preload],
  [/^\/beta2\/?$/, beta2.preload],
  [/^\/beta3\/?$/, beta3.preload],
  [/^\/couples-counseling-ashdod\/?$/, couplesCounselingAshdod.preload],
  [/^\/thank-you-booked\/?$/, thankYouBooked.preload],
  [/^\/thank-you-contact\/?$/, thankYouContact.preload],
  [/^\/about\/?$/, about.preload],
  [/^\/services\/couples\/?$/, couples.preload],
  [/^\/services\/premarital-first-year\/?$/, premarital.preload],
  [/^\/services\/parenting\/?$/, parenting.preload],
  [/^\/services\/mediation\/?$/, mediation.preload],
  [/^\/services\/gifted-parenting\/?$/, gifted.preload],
  [/^\/services\/aliyah-families\/?$/, aliyah.preload],
  [/^\/services\/couples-aliyah-relocation\/?$/, relocation.preload],
  [/^\/services\/late-singleness\/?$/, lateSingleness.preload],
  [/^\/services\/finding-relationship\/?$/, findingRelationship.preload],
  [/^\/blog\/?$/, blogList.preload],
  [/^\/blog\/[^/]+\/?$/, blogPost.preload],
  [/^\/faq\/?$/, faq.preload],
  [/^\/contact\/?$/, contact.preload],
  [/^\/appointment\/?$/, appointment.preload],
  [/^\/accessibility\/?$/, accessibility.preload],
  [/^\/privacy\/?$/, privacy.preload],
  [/^\/terms\/?$/, terms.preload],
];

// The preloader intentionally shares the same module cache as the route
// components, so it must live beside them.
// eslint-disable-next-line react-refresh/only-export-components
export const preloadRoute = (pathname: string) =>
  (routeLoaders.find(([pattern]) => pattern.test(pathname))?.[1] ?? notFound.preload)();

function App() {
  return (
    <Router>
      <ScrollToTop />
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/beta" element={<Beta />} />
          <Route path="/beta2" element={<Beta2 />} />
          <Route path="/beta3" element={<Beta3 />} />
          <Route path="/couples-counseling-ashdod" element={<CouplesCounselingAshdodPage />} />
          <Route path="/thank-you-booked" element={<ThankYouBookedPage />} />
          <Route path="/thank-you-contact" element={<ThankYouContactPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/services/couples" element={<CouplesCounseling />} />
          <Route path="/services/premarital-first-year" element={<PremaritalPage />} />
          <Route path="/services/parenting" element={<ParentingGuidance />} />
          <Route path="/services/mediation" element={<MediationPage />} />
          <Route path="/services/gifted-parenting" element={<GiftedParentingPage />} />
          <Route path="/services/aliyah-families" element={<AliyahFamiliesPage />} />
          <Route path="/services/couples-aliyah-relocation" element={<RelocationPage />} />
          <Route path="/services/late-singleness" element={<LateSinglenessPage />} />
          <Route path="/services/finding-relationship" element={<FindingRelationshipPage />} />
          <Route path="/services/singles-guidance" element={<Navigate to="/services/late-singleness" replace />} />
          <Route path="/blog" element={<BlogList />} />
          <Route path="/blog/:id" element={<BlogPost />} />
          <Route path="/faq" element={<FAQ />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/appointment" element={<AppointmentPage />} />
          <Route path="/b" element={<Navigate to="/" replace />} />
          <Route path="/accessibility" element={<AccessibilityPage />} />
          <Route path="/privacy" element={<PrivacyPolicy />} />
          <Route path="/terms" element={<TermsOfUse />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
