import React, { useRef, useState, useEffect } from 'react';
import { motion, useScroll, useMotionValueEvent } from 'framer-motion';
import { FiArrowDown, FiMessageCircle, FiChevronLeft, FiAward, FiShield, FiHeart } from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import AssessmentModal from './AssessmentModal';
import styles from './BetaPage.module.css';

/* ----------------------------------------------------------------
   Scene thresholds (progress 0…1 over 1000 vh scroll track)
   Scene 1: 0.00 – 0.30   (300 vh, 5 beats  → 60 vh each)
   Scene 2: 0.30 – 0.72   (420 vh, 10 beats → 42 vh each)
   Scene 3: 0.72 – 1.00   (280 vh, 3 beats  → ~93 vh each)
   ---------------------------------------------------------------- */
const S1_END = 0.30;
const S2_END = 0.72;
const S2_SPAN = S2_END - S1_END; // 0.42

const BetaPage: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeScene, setActiveScene] = useState<1 | 2 | 3>(1);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [scene2Progress, setScene2Progress] = useState(0);
  const [isQuizOpen, setIsQuizOpen] = useState(false);

  const v1Ref = useRef<HTMLVideoElement>(null);
  const v2Ref = useRef<HTMLVideoElement>(null);
  const v3Ref = useRef<HTMLVideoElement>(null);

  // ---- Responsive + a11y ----
  useEffect(() => {
    // Mobile check is now handled via CSS classes
  }, []);

  // ---- Scroll tracking ----
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ['start start', 'end end'],
  });

  useMotionValueEvent(scrollYProgress, 'change', (latest) => {
    setCurrentProgress(latest);

    if (latest < S1_END) {
      setActiveScene(1);
    } else if (latest < S2_END) {
      setActiveScene(2);
      setScene2Progress(Math.min(1, Math.max(0, (latest - S1_END) / S2_SPAN)));
    } else {
      setActiveScene(3);
    }
  });

  // ---- Keep active video playing ----
  useEffect(() => {
    const refs = [v1Ref, v2Ref, v3Ref];
    refs.forEach((ref, i) => {
      if (ref.current) {
        if (i + 1 === activeScene && ref.current.paused) {
          ref.current.play().catch(() => {});
        }
      }
    });
  }, [activeScene]);

  // ---- Schema.org ----
  const homeSchema = {
    '@context': 'https://schema.org',
    '@type': 'CounselingService',
    name: 'שירה סהרוני — קשר | ייעוץ זוגי, הנחיית הורים וגישור באשדוד',
    url: 'https://kesher.saharoni.com/beta',
    telephone: '+972-50-0000000',
    address: {
      '@type': 'PostalAddress',
      addressLocality: 'אשדוד',
      addressRegion: 'מחוז הדרום',
      addressCountry: 'IL',
    },
    description:
      'מאיבוד תקשורת לחיבור זוגי יציב. תהליך ממוקד ודיסקרטי בקליניקה באשדוד ובאונליין.',
  };

  /* ==============================================================
     HELPER — build video className
     ============================================================== */
  const videoClass = (scene: number) =>
    `${styles.videoBackground} ${activeScene === scene ? styles.videoVisible : styles.videoHidden}`;

  /* ==============================================================
     SCENE 1 BEAT RANGES (5 beats across 0.00–0.30)
     ============================================================== */
  const s1Beat = (idx: number) => {
    const step = S1_END / 5; // 0.06 each
    return currentProgress >= step * idx && currentProgress < step * (idx + 1);
  };

  /* ==============================================================
     SCENE 2 BEAT RANGES (10 beats across scene2Progress 0..1)
     ============================================================== */
  const s2Beat = (idx: number) => {
    const step = 0.1;
    return scene2Progress >= step * idx && scene2Progress < step * (idx + 1);
  };
  // Last beat (brand reveal) gets everything from 0.9 onward
  const s2LastBeat = scene2Progress >= 0.9;

  /* ==============================================================
     SCENE 3 BEAT RANGES (3 beats across 0.72–1.00)
     ============================================================== */
  const s3Step = (1 - S2_END) / 3; // ~0.093
  const s3Beat = (idx: number) => {
    const start = S2_END + s3Step * idx;
    const end = idx === 2 ? 1.01 : S2_END + s3Step * (idx + 1);
    return currentProgress >= start && currentProgress < end;
  };

  return (
    <>
      <MetaTags
        title="שירה סהרוני | קשר — ייעוץ זוגי, הנחיית הורים וגישור באשדוד"
        description="חוויה סינמטית: מאיבוד תקשורת לחיבור זוגי יציב. תהליך ממוקד, דיסקרטי ומבוסס כלים מעשיים בקליניקה באשדוד ובאונליין."
        canonical="https://kesher.saharoni.com/beta"
      />
      <SchemaOrg data={homeSchema} />

      <main id="main-content" className={styles.scrollytellingPage} dir="rtl">
        {/* Accessible SEO Heading */}
        <h1 className="sr-only">
          שירה סהרוני | קשר — ייעוץ זוגי, הנחיית הורים וגישור באשדוד
        </h1>

        {/* ============================================================
            FLOATING CTA
            ============================================================ */}
        {currentProgress > 0.12 && (
          <motion.a
            initial={{ opacity: 0, scale: 0.8, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            href="https://wa.me/972500000000?text=%D7%A9%D7%9C%D7%95%D7%9D%20%D7%A9%D7%99%D7%A8%D7%94%2C%20%D7%90%D7%A0%D7%99%20%D7%9E%D7%95%D7%A2%D7%A0%D7%99%D7%99%D7%9D%20%D7%91%D7%A9%D7%99%D7%97%D7%AA%20%D7%90%D7%91%D7%97%D7%95%D7%9F%20%D7%95%D7%97%D7%99%D7%91%D7%95%D7%A8%20%D7%96%D7%95%D7%92%D7%99%20%D7%91%D7%90%D7%A9%D7%93%D7%95%D7%93"
            target="_blank"
            rel="noopener noreferrer"
            className={styles.floatingCta}
          >
            <FiMessageCircle className={styles.floatingCtaIcon} />
            <span>לתיאום שיחת אבחון באשדוד / אונליין</span>
          </motion.a>
        )}

        {/* ============================================================
            PART 1 — THE CINEMATIC JOURNEY
            ============================================================ */}
          <div ref={containerRef} className={styles.scrollTrack}>
            <div className={styles.stickyViewport}>

              {/* ---- Scene 1 Videos ---- */}
              <video
                ref={v1Ref}
                src="/videos/scene1.mp4"
                poster="/videos/scene1_poster.jpg"
                autoPlay
                loop
                muted
                playsInline
                preload="auto"
                className={`${videoClass(1)} ${styles.videoDesktop}`}
              />
              <video
                src="/videos/scene1_m.mp4"
                poster="/videos/scene1_poster.jpg"
                autoPlay
                loop
                muted
                playsInline
                preload="auto"
                className={`${videoClass(1)} ${styles.videoMobile}`}
              />

              {/* ---- Scene 2 Videos ---- */}
              <video
                ref={v2Ref}
                src="/videos/scene2.mp4"
                autoPlay
                loop
                muted
                playsInline
                preload="auto"
                className={`${videoClass(2)} ${styles.videoDesktop}`}
              />
              <video
                src="/videos/scene2_m.mp4"
                autoPlay
                loop
                muted
                playsInline
                preload="auto"
                className={`${videoClass(2)} ${styles.videoMobile}`}
              />

              {/* ---- Scene 3 Videos ---- */}
              <video
                ref={v3Ref}
                src="/videos/scene3.mp4"
                autoPlay
                loop
                muted
                playsInline
                preload="auto"
                className={`${videoClass(3)} ${styles.videoDesktop}`}
              />
              <video
                src="/videos/scene3_m.mp4"
                autoPlay
                loop
                muted
                playsInline
                preload="auto"
                className={`${videoClass(3)} ${styles.videoMobile}`}
              />

              {/* ---- Vignette Overlay ---- */}
              <div className={styles.vignetteOverlay} />

              {/* ---- Text Overlay Beats ---- */}
              <div className={styles.textOverlayContainer}>

                {/* ========== SCENE 1 — הזדהות ========== */}
                {activeScene === 1 && (
                  <div className={styles.beatContainer}>
                    {s1Beat(0) && (
                      <motion.div
                        key="s1-b1"
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className={styles.glassCard}
                      >
                        <p className={styles.textBeat}>
                          השעה תשע וחצי בערב. הילדים נרדמו.
                        </p>
                      </motion.div>
                    )}

                    {s1Beat(1) && (
                      <motion.div
                        key="s1-b2"
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className={styles.glassCard}
                      >
                        <p className={styles.textBeat}>
                          הבית שקט, אבל הסלון עמוס במתח.
                        </p>
                      </motion.div>
                    )}

                    {s1Beat(2) && (
                      <motion.div
                        key="s1-b3"
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className={styles.glassCard}
                      >
                        <p className={styles.textBeat}>
                          שניכם יושבים על אותה ספה.
                        </p>
                      </motion.div>
                    )}

                    {s1Beat(3) && (
                      <motion.div
                        key="s1-b4"
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.9 }}
                        className={styles.goldAccentCard}
                      >
                        <p className={`${styles.textBeatBold} ${styles.goldText}`}>
                          ומרגישים בשתי יבשות נפרדות.
                        </p>
                      </motion.div>
                    )}

                    {s1Beat(4) && (
                      <motion.div
                        key="s1-b5"
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className={styles.glassCard}
                      >
                        <p className={styles.textBeat}>
                          מתי הפכנו לשותפים לניהול משק הבית?
                        </p>
                      </motion.div>
                    )}
                  </div>
                )}

                {/* ========== SCENE 2 — הסלמה, גילוי וחשיפה ========== */}
                {activeScene === 2 && (
                  <div className={styles.beatContainer}>
                    {/* Beat 1 */}
                    {s2Beat(0) && (
                      <motion.div
                        key="s2-b1"
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={styles.glassCard}
                      >
                        <p className={styles.textBeat}>
                          השתיקות הפכו לארוכות יותר מהשיחות.
                        </p>
                      </motion.div>
                    )}

                    {/* Beat 2 */}
                    {s2Beat(1) && (
                      <motion.div
                        key="s2-b2"
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={styles.glassCard}
                      >
                        <p className={styles.textBeat}>
                          המריבות הקטנות כבר לא באמת על הכלים.
                        </p>
                      </motion.div>
                    )}

                    {/* Beat 3 */}
                    {s2Beat(2) && (
                      <motion.div
                        key="s2-b3"
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={styles.glassCard}
                      >
                        <p className={styles.textBeat}>
                          שנים של תסכול צבור שוקעות פנימה.
                        </p>
                      </motion.div>
                    )}

                    {/* Beat 4 — ⚠️ Threat / Warning */}
                    {s2Beat(3) && (
                      <motion.div
                        key="s2-b4"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className={styles.warningCard}
                      >
                        <p className={styles.warningText}>
                          ⚠️ אם שום דבר לא ישתנה — זה המסלול לפירוק.
                        </p>
                      </motion.div>
                    )}

                    {/* Beat 5 */}
                    {s2Beat(4) && (
                      <motion.div
                        key="s2-b5"
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={styles.glassCard}
                      >
                        <p className={styles.textBeat}>
                          אבל האמת היא פשוטה יותר.
                        </p>
                      </motion.div>
                    )}

                    {/* Beat 6 — bold */}
                    {s2Beat(5) && (
                      <motion.div
                        key="s2-b6"
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className={styles.loveCard}
                      >
                        <p className={styles.loveText}>
                          זה לא שאין אהבה.
                        </p>
                      </motion.div>
                    )}

                    {/* Beat 7 — bold gold */}
                    {s2Beat(6) && (
                      <motion.div
                        key="s2-b7"
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className={styles.loveCard}
                      >
                        <p className={`${styles.loveText} ${styles.goldText}`}>
                          פשוט איבדתם את השפה.
                        </p>
                      </motion.div>
                    )}

                    {/* Beat 8 */}
                    {s2Beat(7) && (
                      <motion.div
                        key="s2-b8"
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={styles.glassCard}
                      >
                        <p className={styles.textBeat}>
                          איש לא אשם, ואין צורך לשפוט.
                        </p>
                      </motion.div>
                    )}

                    {/* Beat 9 */}
                    {s2Beat(8) && (
                      <motion.div
                        key="s2-b9"
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={styles.glassCard}
                      >
                        <p className={styles.textBeat}>
                          צריך רק את הגישור הנכון.
                        </p>
                      </motion.div>
                    )}

                    {/* Beat 10 — GIANT BRAND REVEAL */}
                    {s2LastBeat && (
                      <motion.div
                        key="s2-reveal"
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ type: 'spring', damping: 15 }}
                        className={styles.brandRevealWrap}
                      >
                        <h2 className={styles.giantBrandText}>
                          שירה סהרוני | קשר
                        </h2>
                        <p className={styles.brandTagline}>
                          ייעוץ זוגי, הנחיית הורים וגישור באשדוד
                        </p>
                      </motion.div>
                    )}
                  </div>
                )}

                {/* ========== SCENE 3 — הפתרון ========== */}
                {activeScene === 3 && (
                  <div className={styles.beatContainer}>
                    {s3Beat(0) && (
                      <motion.div
                        key="s3-b1"
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={styles.glassCard}
                      >
                        <p className={styles.textBeat}>
                          פירוק דפוסי המאבק והחזרת ההקשבה.
                        </p>
                      </motion.div>
                    )}

                    {s3Beat(1) && (
                      <motion.div
                        key="s3-b2"
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={styles.glassCard}
                      >
                        <p className={styles.textBeat}>
                          תהליך ממוקד, דיסקרטי ומבוסס כלים מעשיים.
                        </p>
                      </motion.div>
                    )}

                    {s3Beat(2) && (
                      <motion.div
                        key="s3-b3"
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className={styles.closingGoldCard}
                      >
                        <p className={styles.closingGoldText}>
                          בניית שפה זוגית חדשה שמשאירה אתכם יחד.
                        </p>
                      </motion.div>
                    )}
                  </div>
                )}
              </div>

              {/* ---- Scroll Down Indicator ---- */}
              {currentProgress < 0.92 && (
                <div className={styles.scrollIndicator}>
                  <span className={styles.scrollIndicatorText}>גללו להמשך הסרט</span>
                  <FiArrowDown className={styles.scrollIndicatorIcon} />
                </div>
              )}
            </div>
          </div>

        {/* ============================================================
            PART 2 — THE MARKETING LANDING PAGE
            ============================================================ */}
        <section className={styles.part2Section}>
          <div className={styles.part2Container}>

            {/* ---- HERO / POSITIONING ---- */}
            <div className={styles.heroSection}>
              <span className={styles.heroBadge}>
                קליניקה ממוקדת באשדוד ובפגישות אונליין
              </span>
              <h2 className={styles.heroTitle}>
                מאיבוד תקשורת לחיבור זוגי יציב
              </h2>
              <p className={styles.heroDescription}>
                ייעוץ זוגי, הנחיית הורים וגישור מקצועי בקליניקה הדיסקרטית באשדוד.
                תהליך מובנה בגובה העיניים, המעניק כלים מעשיים להחזרת הקרבה
                והביטחון הביתה.
              </p>

              <div className={styles.ctaRow}>
                <a
                  href="https://wa.me/972500000000?text=%D7%A9%D7%9C%D7%95%D7%9D%20%D7%A9%D7%99%D7%A8%D7%94%2C%20%D7%90%D7%A0%D7%99%20%D7%9E%D7%95%D7%A2%D7%A0%D7%99%D7%99%D7%9D%20%D7%91%D7%A9%D7%99%D7%97%D7%AA%20%D7%90%D7%91%D7%97%D7%95%D7%9F%20%D7%95%D7%97%D7%99%D7%91%D7%95%D7%A8%20%D7%96%D7%95%D7%92%D7%99%20%D7%91%D7%90%D7%A9%D7%93%D7%95%D7%93"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.ctaButtonPrimary}
                >
                  <span>לתיאום שיחת אבחון והתאמה ללא התחייבות</span>
                  <FiChevronLeft className={styles.ctaIcon} />
                </a>
                <button
                  onClick={() => setIsQuizOpen(true)}
                  className={styles.ctaButtonSecondary}
                >
                  <span>להתחלת שאלון האבחון הזוגי (60 שניות)</span>
                </button>
              </div>
            </div>

            {/* ---- TESTIMONIAL ---- */}
            <div className={styles.testimonialSection}>
              <div className={styles.testimonialCard}>
                <div className={styles.starRating}>
                  {[...Array(5)].map((_, i) => (
                    <span key={i} className={styles.star}>★</span>
                  ))}
                </div>
                <blockquote className={styles.testimonialQuote}>
                  &ldquo;הגענו לשירה אחרי שנתיים של שתיקות עמוקות ומריבות בלתי
                  פוסקות. תוך מספר פגישות ממוקדות בקליניקה באשדוד, למדנו לראשונה
                  להקשיב בלי להתגונן. שירה לא שפטה אף אחד מאיתנו — היא פשוט
                  בנתה לנו גשר מחדש.&rdquo;
                </blockquote>
                <div className={styles.testimonialAuthorWrap}>
                  <p className={styles.testimonialAuthor}>מיכל ורועי</p>
                  <p className={styles.testimonialLocation}>
                    אשדוד | תהליך ייעוץ זוגי ממוקד באשדוד
                  </p>
                </div>
              </div>
            </div>

            {/* ---- AUTHORITY & LOCATION ---- */}
            <div className={styles.featureGrid}>
              <div className={styles.featureCard}>
                <div className={styles.featureIconWrap}>
                  <FiShield />
                </div>
                <h3 className={styles.featureTitle}>עורכת דין בהכשרתה ומגשרת</h3>
                <p className={styles.featureDescription}>
                  רקע משפטי וגישורי הנותן תפיסה מובנית, עניינית ונטולת שיפוטיות
                  לניהול קונפליקטים.
                </p>
              </div>

              <div className={styles.featureCard}>
                <div className={styles.featureIconWrap}>
                  <FiHeart />
                </div>
                <h3 className={styles.featureTitle}>התמחות בתקשורת זוגית</h3>
                <p className={styles.featureDescription}>
                  פירוק דפוסי מאבק אוטומטיים, החזרת הקרבה והקשבה רגשית עמוקה
                  בבית.
                </p>
              </div>

              <div className={styles.featureCard}>
                <div className={styles.featureIconWrap}>
                  <FiAward />
                </div>
                <h3 className={styles.featureTitle}>אשדוד והסביבה / אונליין</h3>
                <p className={styles.featureDescription}>
                  קליניקה שקטה ודיסקרטית באשדוד, המשרתת את תושבי אשדוד, גן יבנה,
                  השפלה והדרום.
                </p>
              </div>
            </div>

            {/* ---- QUIZ BANNER ---- */}
            <div className={styles.quizBanner}>
              <div>
                <span className={styles.quizBannerLabel}>
                  אבחון זוגי מהיר (60 שניות)
                </span>
                <h3 className={styles.quizBannerTitle}>
                  האם הזוגיות שלכם נמצאת במסלול של שחיקה או צמיחה?
                </h3>
                <p className={styles.quizBannerDesc}>
                  ענו על 4 שאלות קצרות וקבלו שיקוף מיידי לגבי מצב התקשורת בבית.
                </p>
              </div>
              <button
                onClick={() => setIsQuizOpen(true)}
                className={styles.quizBannerButton}
              >
                להתחלת השאלון הקצר
              </button>
            </div>

            {/* ---- CLOSING ---- */}
            <div className={styles.closingSection}>
              <p className={styles.closingQuote}>
                &ldquo;זוגיות חזקה אינה היעדר קונפליקטים, אלא היכולת לגשר עליהם
                יחד.&rdquo;
              </p>
              <p className={styles.closingCredits}>
                שירה סהרוני — ייעוץ זוגי, הנחיית הורים וגישור באשדוד ובאונליין.
              </p>

              <div className={styles.footerLinks}>
                <a href="/privacy" className={styles.footerLink}>מדיניות פרטיות</a>
                <span className={styles.footerDot}>•</span>
                <a href="/terms" className={styles.footerLink}>תנאי שימוש</a>
                <span className={styles.footerDot}>•</span>
                <a href="/accessibility" className={styles.footerLink}>הצהרת נגישות</a>
              </div>

              <p className={styles.copyright}>
                © 2026 שירה סהרוני — קשר | אשדוד. כל הזכויות שמורות.
              </p>
            </div>

          </div>
        </section>
      </main>

      {/* 60-Second Relationship Assessment Modal */}
      <AssessmentModal isOpen={isQuizOpen} onClose={() => setIsQuizOpen(false)} />
    </>
  );
};

export default BetaPage;
