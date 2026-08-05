import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, useMotionValue, useSpring, useMotionTemplate } from 'framer-motion';

import {
  FiArrowLeft,
  FiCalendar,
  FiCheck,
  FiChevronDown,
  FiCompass,
  FiHeart,
  FiMapPin,
  FiMenu,
  FiMessageCircle,
  FiMonitor,
  FiShield,
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
    accent: 'rose',
    tags: ['תקשורת', 'קרבה', 'אמון'],
  },
  {
    title: 'הדרכת הורים',
    description: 'גבולות ושגרה שנשענים על הבנה וקשר — גם בתקופות עמוסות, רגישות ומבלבלות.',
    link: '/services/parenting',
    icon: FiUsers,
    accent: 'sage',
    tags: ['גבולות', 'שגרה', 'וויסות'],
  },
  {
    title: 'גישור',
    description: 'מרחב ענייני לניהול מחלוקת, הפחתת המתח וניסוח הסכמות שאפשר באמת לקיים.',
    link: '/services/mediation',
    icon: FiCompass,
    accent: 'sand',
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

const process = [
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

const ScrollProgress = () => {
  return <div className={styles.scrollProgress} aria-hidden="true" />;
};

const InteractiveHeroVisual = () => {
  const tiltX = useMotionValue(0);
  const tiltY = useMotionValue(0);
  const glowX = useMotionValue(50);
  const glowY = useMotionValue(50);

  const springConfig = { damping: 1, stiffness: 150, bounce: 0 };
  const smoothTiltX = useSpring(tiltX, springConfig);
  const smoothTiltY = useSpring(tiltY, springConfig);
  const smoothGlowX = useSpring(glowX, springConfig);
  const smoothGlowY = useSpring(glowY, springConfig);
  
  const glowXStr = useMotionTemplate`${smoothGlowX}%`;
  const glowYStr = useMotionTemplate`${smoothGlowY}%`;

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'touch') return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width;
    const y = (event.clientY - bounds.top) / bounds.height;
    
    tiltX.set((0.5 - y) * 15);
    tiltY.set((x - 0.5) * 15);
    glowX.set(x * 100);
    glowY.set(y * 100);
  };

  const resetTilt = () => {
    tiltX.set(0);
    tiltY.set(0);
    glowX.set(50);
    glowY.set(50);
  };

  return (
    <div className={styles.heroVisualStage}>
      <motion.div
        className={styles.heroVisual}
        onPointerMove={handlePointerMove}
        onPointerLeave={resetTilt}
        style={{
          rotateX: smoothTiltX,
          rotateY: smoothTiltY,
          '--glow-x': glowXStr,
          '--glow-y': glowYStr,
        } as unknown as React.CSSProperties}
      >
        <div className={styles.imageFrame}>
          <img
            src="/images/shira-saharoni.webp"
            alt="שירה סהרוני, יועצת זוגית, מנחת הורים ומגשרת"
            width="1271"
            height="1280"
            fetchPriority="high"
          />
          <div className={styles.imageWash} />
          <span className={styles.visualReflection} aria-hidden="true" />
        </div>
        <div className={styles.glassNote}>
          <span className={styles.noteIcon}><FiHeart aria-hidden="true" /></span>
          <p>
            <strong>יועצת זוגית ומנחת הורים</strong>
          </p>
        </div>
      </motion.div>
      <span className={styles.visualHalo} aria-hidden="true" />
    </div>
  );
};

const Beta3Page: React.FC = () => {
  const carouselRef = React.useRef<HTMLDivElement>(null);
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
    <div className={styles.page} dir="rtl">
      <MetaTags
        title="שירה סהרוני — ייעוץ זוגי והנחיית הורים"
        description={SITE_CONFIG.description}
        canonical={`${SITE_CONFIG.url}/`}
        image="/images/shira-saharoni.webp"
      />
      <SchemaOrg data={homeSchema} />
      <ScrollProgress />

      <div className={styles.ambient} aria-hidden="true">
        <span className={styles.orbOne} />
        <span className={styles.orbTwo} />
        <span className={styles.gridTexture} />
      </div>

      <header className={styles.header}>
        <div className={styles.headerInner}>
          <motion.a href="#top" className={styles.brand} aria-label="שירה סהרוני — לראש העמוד" whileTap={{ scale: 0.95 }} transition={{ type: 'spring', bounce: 0, duration: 0.4 }}>
            <span className={styles.brandMark}>ש</span>
            <span>
              <strong>שירה סהרוני</strong>
              <small>ייעוץ · הורות · גישור</small>
            </span>
          </motion.a>

          <nav className={styles.desktopNav} aria-label="ניווט ראשי">
            <motion.a href="#services">איך אוכל לעזור</motion.a>
            <motion.a href="#about">אודות</motion.a>
            <motion.a href="#process">איך זה עובד</motion.a>
            <MotionLink to="/blog">מאמרים</MotionLink>
          </nav>

          <div className={styles.headerActions}>
            <MotionLink to={SITE_CONFIG.links.appointment} className={styles.headerCta}>
              קביעת פגישה
              <FiArrowLeft aria-hidden="true" />
            </MotionLink>
            <button
              type="button"
              className={styles.menuButton}
              aria-label={menuOpen ? 'סגירת תפריט' : 'פתיחת תפריט'}
              aria-expanded={menuOpen}
              aria-controls="main-mobile-menu"
              onClick={() => setMenuOpen((open) => !open)}
            >
              {menuOpen ? <FiX aria-hidden="true" /> : <FiMenu aria-hidden="true" />}
            </button>
          </div>
        </div>

        {menuOpen && (
          <nav id="main-mobile-menu" className={styles.mobileNav} aria-label="ניווט ראשי">
            <motion.a href="#services" onClick={() => setMenuOpen(false)}>איך אוכל לעזור</motion.a>
            <motion.a href="#about" onClick={() => setMenuOpen(false)}>אודות</motion.a>
            <motion.a href="#process" onClick={() => setMenuOpen(false)}>איך זה עובד</motion.a>
            <MotionLink to="/blog" onClick={() => setMenuOpen(false)}>מאמרים</MotionLink>
            <MotionLink to={SITE_CONFIG.links.appointment} onClick={() => setMenuOpen(false)}>קביעת פגישה</MotionLink>
          </nav>
        )}
      </header>

      <main id="main-content" className={styles.main}>
        <motion.section initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ type: 'spring', bounce: 0, duration: 0.6 }} id="top" className={styles.hero}>
          <div className={styles.heroCopy}>
            <div className={styles.eyebrow}>
              <span className={styles.pulse} aria-hidden="true" />
              פגישות באשדוד ובאונליין
            </div>
            <h1>
              אפשר לבחור לבנות
              <span> את הקשר אחרת. יחד.</span>
            </h1>
            <p className={styles.heroLead}>
              גם כשהשיחות נתקעות והמרחק גדל, אפשר להבין מה קורה ביניכם,
              לבחור צעדים חדשים וליצור תנועה שמחזירה תקווה לקשר.
            </p>
            <div className={styles.heroActions}>
              <MotionLink to={SITE_CONFIG.links.appointment} className={styles.primaryCta} whileTap={{ scale: 0.97 }} transition={{ type: 'spring', bounce: 0, duration: 0.4 }}>
                <FiCalendar aria-hidden="true" />
                קביעת פגישת ייעוץ
              </MotionLink>
              <motion.a href="#services" className={styles.secondaryCta} whileTap={{ scale: 0.97 }} transition={{ type: 'spring', bounce: 0, duration: 0.4 }}>
                למצוא את הליווי המתאים
                <FiChevronDown aria-hidden="true" />
              </motion.a>
            </div>
            <motion.a href={SITE_CONFIG.links.whatsapp} className={styles.heroWhatsapp} whileTap={{ scale: 0.97 }} transition={{ type: 'spring', bounce: 0, duration: 0.4 }}>
              <FiMessageCircle aria-hidden="true" />
              מעדיפים להתחיל בהודעה? כתבו לי ב־WhatsApp
              <FiArrowLeft aria-hidden="true" />
            </motion.a>
            <div className={styles.trustRow} aria-label="פרטי השירות">
              <span><FiMapPin aria-hidden="true" /> אשדוד</span>
              <span><FiMonitor aria-hidden="true" /> אונליין</span>
              <span><FiShield aria-hidden="true" /> מרחב אישי ומכבד</span>
            </div>
          </div>

          <InteractiveHeroVisual />
        </motion.section>

        <motion.section initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ type: 'spring', bounce: 0, duration: 0.6 }} className={styles.signalBar} aria-label="תחומי העיסוק של שירה">
          <span>ייעוץ זוגי</span>
          <i aria-hidden="true" />
          <span>הנחיית הורים</span>
          <i aria-hidden="true" />
          <span>גישור</span>
          <i aria-hidden="true" />
          <span>ליווי בתקופות מעבר</span>
        </motion.section>

        <motion.section initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ type: 'spring', bounce: 0, duration: 0.6 }} id="services" className={`${styles.section} ${styles.revealSection}`}>
          <div className={styles.sectionHeading}>
            <span className={styles.kicker}>לא צריך לדעת מראש מה הכותרת המדויקת לקושי.</span>
            <h2>מתחילים מהמקום שבו<br />הקשר מבקש שינוי.</h2>
            <p>אפשר להתחיל מהנושא שהכי מעסיק אתכם עכשיו. את החיבורים בין הדברים נבין יחד.</p>
          </div>

          <div className={styles.serviceGrid}>
            {services.map(({ title, description, link, icon: Icon, accent, tags }, index) => (
              <MotionLink
                to={link}
                className={`${styles.serviceCard} ${styles[accent]} ${index < 2 ? styles.primaryService : styles.secondaryService}`}
                key={title}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.97 }}
                transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
              >
                <span className={styles.serviceIcon}><Icon aria-hidden="true" /></span>
                <span
                  className={styles.serviceIndex}
                  data-index={`0${index + 1}`}
                  aria-hidden="true"
                />
                <h3>{title}</h3>
                <p>{description}</p>
                <span className={styles.serviceTags} aria-label={`נושאים מרכזיים ב${title}`}>
                  {tags.map((tag) => <small key={tag}>{tag}</small>)}
                </span>
                <span className={styles.cardLink}>
                  לקריאה נוספת
                  <FiArrowLeft aria-hidden="true" />
                </span>
              </MotionLink>
            ))}
          </div>
        </motion.section>

        <motion.section initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ type: 'spring', bounce: 0, duration: 0.6 }} className={`${styles.section} ${styles.trustSection} ${styles.revealSection}`}>
          <div className={styles.trustHeading}>
            <span className={styles.kicker}>אמון נבנה בחוויה</span>
            <h2>מה משתנה כשמצליחים לדבר אחרת.</h2>
            <p>הפרטים המזהים הושמטו כדי לשמור על פרטיות הפונים.</p>
          </div>
          <div className={styles.carouselContainer} ref={carouselRef}>
            <motion.div 
              className={styles.quoteGrid}
              drag="x"
              dragConstraints={carouselRef}
              whileTap={{ cursor: "grabbing" }}
              dragElastic={0.2}
              transition={{ type: 'spring', bounce: 0, duration: 0.5 }}
            >
              {testimonials.map((testimonial, index) => (
                <blockquote
                  className={`${styles.quoteCard} ${index === 0 ? styles.featuredQuote : ''}`}
                  key={testimonial.author}
                >
                  <span className={styles.quoteType}>{testimonial.type}</span>
                  <FiMessageCircle aria-hidden="true" />
                  <p>“{testimonial.text}”</p>
                  <footer>{testimonial.author}</footer>
                </blockquote>
              ))}
            </motion.div>
          </div>
        </motion.section>

        <motion.section initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ type: 'spring', bounce: 0, duration: 0.6 }} id="about" className={`${styles.section} ${styles.aboutSection} ${styles.revealSection}`}>
          <div className={styles.aboutVisual}>
            <div className={styles.aboutImage}>
              <img
                src="/images/generated/site/home-hero.jpg"
                alt="חדר הייעוץ של שירה סהרוני באשדוד"
                width="1600"
                height="900"
                loading="lazy"
              />
            </div>
            <div className={styles.aboutQuote}>
              <FiMessageCircle aria-hidden="true" />
              <p><strong>יש דרך לדבר.</strong><br />גם כשכבר קשה<br />לשמוע.</p>
            </div>
          </div>

          <div className={styles.aboutCopy}>
            <span className={styles.kicker}>נעים מאוד, שירה</span>
            <h2>מקצועיות שמחזיקה את המורכבות. שיחה שנשארת אנושית.</h2>
            <p className={styles.aboutLead}>
              אני מלווה זוגות והורים ברגעים שבהם התקשורת נתקעת, העומס גובר
              או הבית מבקש דרך חדשה. המטרה שלי היא להקשיב ולהבין יחד את הקושי,
              ולחבר אותו לצעדים מעשיים שאפשר ליישם בחיים עצמם.
            </p>
            <p>
              יחד נפרק מצבים שנראים מסובכים, נזהה את הדפוסים שחוזרים
              ונבנה אפשרות אחרת — רגישה, בהירה ומותאמת למשפחה שלכם.
            </p>
            <ul className={styles.focusList}>
              {focusAreas.map((area) => (
                <li key={area}><FiCheck aria-hidden="true" />{area}</li>
              ))}
            </ul>
            <aside className={styles.professionalProfile} aria-label="הכשרה מקצועית">
              <span>הכשרה מקצועית מוסמכת</span>
              <p>
                העשייה שלי נשענת על הכשרה בייעוץ זוגי ומשפחתי, בהנחיית הורים
                קבוצתית ופרטנית עם התמחות ב־ADHD, ובגישור.
              </p>
              <small>
                ההכשרות כוללות לימודים מקצועיים, תעודות ופרקטיקום מעשי.
              </small>
            </aside>
            <MotionLink to="/about" className={styles.textLink}>
              עוד עליי ועל אופן העבודה
              <FiArrowLeft aria-hidden="true" />
            </MotionLink>
            <p className={styles.legalBackground}>רקע נוסף: עורכת דין בהכשרתי.</p>
          </div>
        </motion.section>

        <motion.section initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ type: 'spring', bounce: 0, duration: 0.6 }} id="process" className={`${styles.section} ${styles.processSection} ${styles.revealSection}`}>
          <div className={styles.sectionHeading}>
            <span className={styles.kicker}>איך מתחילים</span>
            <h2>בהירות לפני הכול.</h2>
            <p>לא צריך להגיע עם ניסוח מדויק. מתחילים ממה שקשה עכשיו ומתקדמים צעד אחר צעד.</p>
          </div>
          <div className={styles.processGrid}>
            {process.map((step) => (
              <article
                className={styles.processCard}
                key={step.number}
                style={{ '--process-delay': `${Number(step.number) * 65}ms` } as React.CSSProperties}
              >
                <span className={styles.processNumber}>{step.number}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </article>
            ))}
          </div>
        </motion.section>

        <motion.section initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-50px" }} transition={{ type: 'spring', bounce: 0, duration: 0.6 }} className={`${styles.finalCta} ${styles.revealSection}`}>
          <div>
            <span className={styles.kicker}>אפשר להתחיל מכאן</span>
            <h2>השיחה הראשונה לא חייבת לפתור הכול.<br />היא רק צריכה לפתוח דרך.</h2>
          </div>
          <div className={styles.finalActions}>
            <MotionLink to={SITE_CONFIG.links.appointment} className={styles.lightCta}>
              <FiCalendar aria-hidden="true" />
              קביעת פגישה
            </MotionLink>
            <motion.a href={SITE_CONFIG.links.whatsapp} className={styles.whatsappCta}>
              <FiMessageCircle aria-hidden="true" />
              כתבו לי ב־WhatsApp
            </motion.a>
          </div>
        </motion.section>
      </main>

      <aside className={styles.quickDock} aria-label="אפשרויות ליצירת קשר">
        <span className={styles.quickDockLabel}>אפשר להתחיל בדרך שנוחה לכם</span>
        <MotionLink to={SITE_CONFIG.links.appointment}>
          <FiCalendar aria-hidden="true" />
          <span>פגישה</span>
        </MotionLink>
        <motion.a href={SITE_CONFIG.links.whatsapp}>
          <FiMessageCircle aria-hidden="true" />
          <span>WhatsApp</span>
        </motion.a>
      </aside>

      <footer className={styles.footer}>
        <div className={styles.footerBrand}>
          <span className={styles.brandMark}>ש</span>
          <div>
            <strong>שירה סהרוני</strong>
            <small>ייעוץ זוגי · הנחיית הורים · גישור</small>
          </div>
        </div>
        <div className={styles.footerLinks}>
          <MotionLink to="/contact">יצירת קשר</MotionLink>
          <MotionLink to="/blog">מאמרים</MotionLink>
          <MotionLink to="/privacy">פרטיות</MotionLink>
          <MotionLink to="/accessibility">נגישות</MotionLink>
        </div>
      </footer>
    </div>
  );
};

export default Beta3Page;
