import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, useMotionValue, useSpring, AnimatePresence } from 'framer-motion';
import {
  FiArrowLeft,
  FiCalendar,
  FiCheck,
  FiChevronDown,
  FiCompass,
  FiHeart,
  FiMenu,
  FiMessageCircle,
  FiUsers,
  FiX,
} from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { homeSchema } from '../../constants/homeSchema';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './Beta3Page.module.css';

const MotionLink = motion.create(Link);

const services = [
  {
    title: 'ייעוץ זוגי',
    description: 'כשהשיחות מסתיימות שוב באותו מקום, נלמד לזהות את הדפוס וליצור דרך חדשה להיפגש.',
    link: '/services/couples',
    icon: FiHeart,
    iconClass: styles.iconRose,
    accent: 'large',
    tags: ['תקשורת', 'קרבה', 'אמון'],
  },
  {
    title: 'הדרכת הורים',
    description: 'גבולות ושגרה שנשענים על הבנה וקשר — גם בתקופות עמוסות, רגישות ומבלבלות.',
    link: '/services/parenting',
    icon: FiUsers,
    iconClass: styles.iconSage,
    accent: 'large',
    tags: ['גבולות', 'שגרה', 'וויסות'],
  },
  {
    title: 'גישור ופתרון מחלוקות',
    description: 'מרחב ענייני לניהול מחלוקת, הפחתת המתח וניסוח הסכמות שאפשר באמת לקיים.',
    link: '/services/mediation',
    icon: FiCompass,
    iconClass: styles.iconSand,
    accent: 'full',
    tags: ['הקשבה', 'הסכמות', 'בהירות'],
  },
];

const focusAreas = [
  'זוגיות בתקופות של ריחוק ושחיקה',
  'הורות לילדים מחוננים וילדים עם ADHD',
  'הכנה לנישואים והשנה הראשונה',
  'משפחות בעלייה, בחזרה לישראל וברילוקיישן',
  'רווקות מאוחרת וליווי למציאת זוגיות',
];

const processSteps = [
  {
    number: '01',
    title: 'מתחילים במה שקורה עכשיו',
    text: 'ממפים יחד את הקושי, את הרגעים שבהם הוא מופיע ואת השינוי שהכי חשוב לכם להרגיש.',
  },
  {
    number: '02',
    title: 'מבינים את הדפוס',
    text: 'מזהים מה מפעיל אתכם, מה משמר את התקיעות ואיפה אפשר לייצר תגובה חדשה.',
  },
  {
    number: '03',
    title: 'מתרגלים דרך אחרת',
    text: 'יוצאים מהפגישה עם כיוון ברור וכלים שאפשר לנסות בבית, בקצב שמתאים לכם.',
  },
];

const testimonials = [
  {
    text: 'הגענו לשירה בשיא המשבר. היא עזרה לנו להוריד את גובה הלהבות ולדבר בפעם הראשונה מזה שנים.',
    author: 'א׳ ו־מ׳, אשדוד',
    type: 'ייעוץ זוגי',
  },
  {
    text: 'הדרכת ההורים עזרה לנו להבין טוב יותר את הקושי של הבן שלנו ולבנות שגרה רגועה וברורה יותר.',
    author: 'משפחת ל׳, גן יבנה',
    type: 'הדרכת הורים',
  },
  {
    text: 'הרגישות והכלים המעשיים נתנו לנו דרך להתחיל להתקרב מחדש.',
    author: 'ד׳ ס׳, דרום',
    type: 'ליווי זוגי',
  },
];

/* Apple 3D Interactive Hero Card */
const GlassHeroCard = () => {
  const tiltX = useMotionValue(0);
  const tiltY = useMotionValue(0);

  const springConfig = { damping: 15, stiffness: 150, mass: 0.5 };
  const smoothTiltX = useSpring(tiltX, springConfig);
  const smoothTiltY = useSpring(tiltY, springConfig);

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'touch') return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width;
    const y = (event.clientY - bounds.top) / bounds.height;
    
    tiltX.set((0.5 - y) * 12);
    tiltY.set((x - 0.5) * 12);
  };

  const resetTilt = () => {
    tiltX.set(0);
    tiltY.set(0);
  };

  return (
    <div className={styles.heroVisualStage}>
      <motion.div
        className={styles.glassHeroCard}
        onPointerMove={handlePointerMove}
        onPointerLeave={resetTilt}
        style={{
          rotateX: smoothTiltX,
          rotateY: smoothTiltY,
        }}
        whileHover={{ scale: 1.02 }}
        transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
      >
        <div className={styles.heroImageContainer}>
          <img
            src="/images/shira-saharoni.webp"
            alt="שירה סהרוני, יועצת זוגית, מנחת הורים ומגשרת"
            width="1271"
            height="1280"
          />
        </div>
        <div className={styles.floatingGlassBadge}>
          <div className={styles.badgeIcon}>
            <FiHeart />
          </div>
          <div className={styles.badgeText}>
            <strong>שירה סהרוני</strong>
            <span>ייעוץ זוגי · הדרכת הורים · גישור</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

const Beta3Page: React.FC = () => {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [menuOpen]);

  return (
    <div className={styles.page}>
      <MetaTags
        title="שירה סהרוני — ייעוץ זוגי והנחיית הורים"
        description={SITE_CONFIG.description}
        canonical={`${SITE_CONFIG.url}/`}
        image="/images/shira-saharoni.webp"
      />
      <SchemaOrg data={homeSchema} />

      {/* Ambient Apple Glow */}
      <div className={styles.ambient} aria-hidden="true">
        <span className={styles.orbOne} />
        <span className={styles.orbTwo} />
        <span className={styles.orbThree} />
      </div>

      {/* Floating Apple Header */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <MotionLink 
            to="/" 
            className={styles.brand} 
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.96 }}
            transition={{ type: 'spring', bounce: 0, duration: 0.3 }}
          >
            <div className={styles.brandMark}>ש</div>
            <div className={styles.brandText}>
              <span className={styles.brandName}>שירה סהרוני</span>
              <span className={styles.brandTag}>ייעוץ זוגי · הורות</span>
            </div>
          </MotionLink>

          <nav className={styles.desktopNav} aria-label="ניווט ראשי">
            <a href="#services">איך אוכל לעזור</a>
            <a href="#about">אודות</a>
            <a href="#process">תהליך עבודה</a>
            <Link to="/blog">מאמרים</Link>
          </nav>

          <div className={styles.headerActions}>
            <MotionLink 
              to={SITE_CONFIG.links.appointment} 
              className={styles.headerCta}
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.96 }}
              transition={{ type: 'spring', bounce: 0, duration: 0.3 }}
            >
              קביעת פגישה
              <FiArrowLeft />
            </MotionLink>
            <button
              type="button"
              className={styles.menuButton}
              aria-label="תפריט"
              onClick={() => setMenuOpen(!menuOpen)}
            >
              {menuOpen ? <FiX /> : <FiMenu />}
            </button>
          </div>
        </div>
      </header>

      {/* Apple Drag Bottom Sheet Mobile Menu */}
      <AnimatePresence>
        {menuOpen && (
          <>
            <motion.div 
              className={styles.mobileSheetOverlay}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMenuOpen(false)}
            />
            <motion.div 
              className={styles.mobileSheet}
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
              drag="y"
              dragConstraints={{ top: 0 }}
              dragElastic={0.2}
              onDragEnd={(_, info) => {
                if (info.offset.y > 100 || info.velocity.y > 500) {
                  setMenuOpen(false);
                }
              }}
            >
              <div className={styles.sheetHandle} />
              <nav className={styles.mobileSheetNav}>
                <a href="#services" onClick={() => setMenuOpen(false)}>איך אוכל לעזור</a>
                <a href="#about" onClick={() => setMenuOpen(false)}>אודות</a>
                <a href="#process" onClick={() => setMenuOpen(false)}>תהליך עבודה</a>
                <Link to="/blog" onClick={() => setMenuOpen(false)}>מאמרים</Link>
                <Link to={SITE_CONFIG.links.appointment} onClick={() => setMenuOpen(false)}>קביעת פגישה</Link>
              </nav>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <main id="main-content" className={styles.main}>
        {/* Apple Hero Section */}
        <section className={styles.hero}>
          <motion.div 
            className={styles.heroCopy}
            initial={{ opacity: 0, y: 25 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', bounce: 0, duration: 0.6 }}
          >
            <div className={styles.applePill}>
              <span className={styles.greenDot} />
              פגישות בקליניקה באשדוד ובאונליין
            </div>
            <h1 className={styles.heroTitle}>
              אפשר לבנות
              <span className={styles.gradientText}>את הקשר אחרת. יחד.</span>
            </h1>
            <p className={styles.heroLead}>
              גם כשהשיחות נתקעות והמרחק גדל, אפשר להבין מה מפעיל אתכם ולייצר דרך חדשה שמחזירה את הקרבה והתקווה.
            </p>
            <div className={styles.heroActions}>
              <MotionLink 
                to={SITE_CONFIG.links.appointment} 
                className={styles.primaryAppleBtn}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.96 }}
                transition={{ type: 'spring', bounce: 0, duration: 0.3 }}
              >
                <FiCalendar />
                תיאום שיחת ייעוץ
              </MotionLink>
              <motion.a 
                href="#services" 
                className={styles.secondaryAppleBtn}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.96 }}
                transition={{ type: 'spring', bounce: 0, duration: 0.3 }}
              >
                מסלולי ליווי
                <FiChevronDown />
              </motion.a>
            </div>
            <motion.a 
              href={SITE_CONFIG.links.whatsapp} 
              className={styles.heroWhatsapp}
              whileHover={{ x: -4 }}
              transition={{ type: 'spring', bounce: 0, duration: 0.3 }}
            >
              <FiMessageCircle />
              מעדיפים הודעה? כתבו לי ב-WhatsApp
              <FiArrowLeft />
            </motion.a>
          </motion.div>

          <GlassHeroCard />
        </section>

        {/* Bento Grid Services */}
        <section id="services" className={styles.section}>
          <motion.div 
            className={styles.sectionHeader}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ type: 'spring', bounce: 0, duration: 0.6 }}
          >
            <span className={styles.sectionKicker}>תחומי ליווי</span>
            <h2 className={styles.sectionTitle}>איך אוכל לעזור לכם?</h2>
            <p className={styles.sectionSubtitle}>
              מתחילים מהמקום שבו הקשר מבקש שינוי. את החיבורים בין הדברים נבין יחד.
            </p>
          </motion.div>

          <div className={styles.bentoGrid}>
            {services.map((service) => {
              const Icon = service.icon;
              const isFull = service.accent === 'full';
              return (
                <MotionLink
                  to={service.link}
                  key={service.title}
                  className={`${styles.bentoCard} ${isFull ? styles.bentoFull : styles.bentoLarge}`}
                  whileHover={{ scale: 1.02, y: -4 }}
                  whileTap={{ scale: 0.98 }}
                  transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
                >
                  <div>
                    <div className={`${styles.bentoCardIcon} ${service.iconClass}`}>
                      <Icon />
                    </div>
                    <h3>{service.title}</h3>
                    <p>{service.description}</p>
                    <div className={styles.bentoTagList}>
                      {service.tags.map((tag) => (
                        <span key={tag} className={styles.bentoTag}>{tag}</span>
                      ))}
                    </div>
                  </div>
                  <div className={styles.cardArrow}>
                    קראי עוד <FiArrowLeft />
                  </div>
                </MotionLink>
              );
            })}
          </div>
        </section>

        {/* About Section (#about) */}
        <section id="about" className={styles.section}>
          <div className={styles.aboutGrid}>
            <motion.div 
              className={styles.aboutVisual}
              initial={{ opacity: 0, scale: 0.95 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ type: 'spring', bounce: 0, duration: 0.6 }}
            >
              <div className={styles.aboutImageFrame}>
                <img
                  src="/images/generated/site/home-hero.jpg"
                  alt="חדר הייעוץ של שירה סהרוני באשדוד"
                  width="1600"
                  height="900"
                  loading="lazy"
                />
              </div>
            </motion.div>

            <motion.div 
              className={styles.aboutCopy}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ type: 'spring', bounce: 0, duration: 0.6 }}
            >
              <span className={styles.sectionKicker}>נעים מאוד, שירה</span>
              <h2>מקצועיות שמחזיקה את המורכבות. שיחה שנשארת אנושית.</h2>
              <p className={styles.aboutLead}>
                אני מלווה זוגות והורים ברגעים שבהם התקשורת נתקעת, העומס גובר או הבית מבקש דרך חדשה. המטרה שלי היא להקשיב ולפרק יחד מצבים מסובכים לצעדים מעשיים שאפשר ליישם בחיים עצמם.
              </p>
              
              <ul className={styles.focusGrid}>
                {focusAreas.map((area) => (
                  <motion.li 
                    key={area} 
                    className={styles.focusItem}
                    whileHover={{ scale: 1.02 }}
                    transition={{ type: 'spring', bounce: 0, duration: 0.2 }}
                  >
                    <FiCheck className={styles.focusCheckIcon} />
                    <span>{area}</span>
                  </motion.li>
                ))}
              </ul>

              <div className={styles.credentialGlassCard}>
                <span className={styles.credentialTitle}>הכשרה מקצועית מוסמכת</span>
                <p className={styles.credentialText}>
                  העשייה שלי נשענת על הכשרה בייעוץ זוגי ומשפחתי, בהנחיית הורים (עם התמחות ב-ADHD), ובגישור. רקע נוסף: עורכת דין בהכשרתי.
                </p>
              </div>
            </motion.div>
          </div>
        </section>

        {/* Process Section (#process) */}
        <section id="process" className={styles.section}>
          <motion.div 
            className={styles.sectionHeader}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ type: 'spring', bounce: 0, duration: 0.6 }}
          >
            <span className={styles.sectionKicker}>תהליך עבודה</span>
            <h2 className={styles.sectionTitle}>בהירות לפני הכול.</h2>
            <p className={styles.sectionSubtitle}>
              לא צריך להגיע עם ניסוח מדויק. מתחילים ממה שקשה עכשיו ומתקדמים צעד אחר צעד.
            </p>
          </motion.div>

          <div className={styles.processGrid}>
            {processSteps.map((step) => (
              <motion.div 
                key={step.number} 
                className={styles.processCard}
                whileHover={{ scale: 1.03, y: -4 }}
                transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
              >
                <span className={styles.processNumber}>{step.number}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Apple Testimonials 3-Column Grid (Desktop) / Scroll Snap (Mobile) */}
        <section className={styles.section}>
          <motion.div 
            className={styles.sectionHeader}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ type: 'spring', bounce: 0, duration: 0.6 }}
          >
            <span className={styles.sectionKicker}>מחוויות המטופלים</span>
            <h2 className={styles.sectionTitle}>מה משתנה בקשר.</h2>
          </motion.div>

          <div className={styles.testimonialsGrid}>
            {testimonials.map((t) => (
              <motion.div 
                key={t.author} 
                className={styles.quoteCard}
                whileHover={{ scale: 1.02, y: -4 }}
                transition={{ type: 'spring', bounce: 0, duration: 0.3 }}
              >
                <span className={styles.quoteType}>{t.type}</span>
                <p className={styles.quoteText}>"{t.text}"</p>
                <span className={styles.quoteAuthor}>{t.author}</span>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Final Apple Glass Banner CTA */}
        <motion.section 
          className={styles.finalBanner}
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ type: 'spring', bounce: 0, duration: 0.6 }}
        >
          <h2>השיחה הראשונה לא חייבת לפתור הכול.<br />היא רק צריכה לפתוח דרך.</h2>
          <div className={styles.finalBannerActions}>
            <MotionLink 
              to={SITE_CONFIG.links.appointment} 
              className={styles.primaryAppleBtn}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.96 }}
            >
              <FiCalendar />
              תיאום פגישת ייעוץ
            </MotionLink>
            <motion.a 
              href={SITE_CONFIG.links.whatsapp} 
              className={styles.secondaryAppleBtn}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.96 }}
            >
              <FiMessageCircle />
              כתבו לי ב-WhatsApp
            </motion.a>
          </div>
        </motion.section>
      </main>

      {/* Floating Apple Dock */}
      <div className={styles.appleDockContainer}>
        <motion.div 
          className={styles.appleDock}
          initial={{ y: 50, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ type: 'spring', bounce: 0, duration: 0.5 }}
        >
          <MotionLink 
            to={SITE_CONFIG.links.appointment} 
            className={`${styles.dockItem} ${styles.dockPrimary}`}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <FiCalendar />
            <span>פגישה</span>
          </MotionLink>
          <motion.a 
            href={SITE_CONFIG.links.whatsapp} 
            className={styles.dockItem}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <FiMessageCircle />
            <span>WhatsApp</span>
          </motion.a>
          <motion.a 
            href="#services" 
            className={styles.dockItem}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <FiCompass />
            <span>שירותים</span>
          </motion.a>
        </motion.div>
      </div>

      {/* Footer */}
      <footer className={styles.footer}>
        <div className={styles.footerBrand}>
          <div className={styles.brandMark}>ש</div>
          <div>
            <strong>שירה סהרוני</strong>
            <br />
            <small style={{ color: 'var(--apple-muted)' }}>ייעוץ זוגי · הדרכת הורים · גישור</small>
          </div>
        </div>
        <div className={styles.footerLinks}>
          <Link to="/contact">יצירת קשר</Link>
          <Link to="/blog">מאמרים</Link>
          <Link to="/privacy">פרטיות</Link>
          <Link to="/accessibility">נגישות</Link>
        </div>
      </footer>
    </div>
  );
};

export default Beta3Page;
