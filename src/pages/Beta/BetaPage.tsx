import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
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
  FiStar,
  FiUsers,
  FiX,
} from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './BetaPage.module.css';

const services = [
  {
    title: 'ייעוץ זוגי',
    description: 'לצאת מאותו ויכוח שחוזר שוב ושוב, להבין את הדפוס ולבנות דרך אחרת לדבר.',
    link: '/services/couples',
    icon: FiHeart,
    accent: 'rose',
  },
  {
    title: 'הדרכת הורים',
    description: 'לעשות סדר בתגובות, בגבולות ובשגרה — בלי לאבד את הקשר עם הילד.',
    link: '/services/parenting',
    icon: FiUsers,
    accent: 'sage',
  },
  {
    title: 'גישור',
    description: 'לנהל מחלוקת באופן ענייני, להפחית את המתח ולנסח הסכמות שאפשר לקיים.',
    link: '/services/mediation',
    icon: FiCompass,
    accent: 'sand',
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

const BetaPage: React.FC = () => {
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
        title="Beta — שירה סהרוני"
        description="גרסת ניסוי לעמוד הבית של שירה סהרוני — ייעוץ זוגי, הנחיית הורים וגישור באשדוד ובאונליין."
        canonical={`${SITE_CONFIG.url}/b`}
        image="/images/shira-saharoni.webp"
        noIndex
      />

      <div className={styles.ambient} aria-hidden="true">
        <span className={styles.orbOne} />
        <span className={styles.orbTwo} />
        <span className={styles.gridTexture} />
      </div>

      <header className={styles.header}>
        <div className={styles.headerInner}>
          <a href="#top" className={styles.brand} aria-label="שירה סהרוני — לראש העמוד">
            <span className={styles.brandMark}>ש</span>
            <span>
              <strong>שירה סהרוני</strong>
              <small>ייעוץ · הורות · גישור</small>
            </span>
          </a>

          <nav className={styles.desktopNav} aria-label="ניווט בגרסת הבטא">
            <a href="#services">איך אוכל לעזור</a>
            <a href="#about">אודות</a>
            <a href="#process">איך זה עובד</a>
            <Link to="/blog">מאמרים</Link>
          </nav>

          <div className={styles.headerActions}>
            <span className={styles.betaTag}>BETA</span>
            <Link to={SITE_CONFIG.links.appointment} className={styles.headerCta}>
              קביעת פגישה
              <FiArrowLeft aria-hidden="true" />
            </Link>
            <button
              type="button"
              className={styles.menuButton}
              aria-label={menuOpen ? 'סגירת תפריט' : 'פתיחת תפריט'}
              aria-expanded={menuOpen}
              aria-controls="beta-mobile-menu"
              onClick={() => setMenuOpen((open) => !open)}
            >
              {menuOpen ? <FiX aria-hidden="true" /> : <FiMenu aria-hidden="true" />}
            </button>
          </div>
        </div>

        {menuOpen && (
          <nav id="beta-mobile-menu" className={styles.mobileNav} aria-label="ניווט בגרסת הבטא למובייל">
            <a href="#services" onClick={() => setMenuOpen(false)}>איך אוכל לעזור</a>
            <a href="#about" onClick={() => setMenuOpen(false)}>אודות</a>
            <a href="#process" onClick={() => setMenuOpen(false)}>איך זה עובד</a>
            <Link to="/blog" onClick={() => setMenuOpen(false)}>מאמרים</Link>
            <Link to={SITE_CONFIG.links.appointment} onClick={() => setMenuOpen(false)}>קביעת פגישה</Link>
          </nav>
        )}
      </header>

      <main id="main-content" className={styles.main}>
        <section id="top" className={styles.hero}>
          <div className={styles.heroCopy}>
            <div className={styles.eyebrow}>
              <span className={styles.pulse} aria-hidden="true" />
              פגישות באשדוד ובאונליין
            </div>
            <h1>
              לא חייבים להישאר
              <span> במקום שבו הקשר נתקע.</span>
            </h1>
            <p className={styles.heroLead}>
              ייעוץ זוגי, הנחיית הורים וגישור בגישה רגישה, בהירה ומעשית —
              כדי להבין מה קורה ביניכם ולהתחיל לזוז אחרת.
            </p>
            <div className={styles.heroActions}>
              <Link to={SITE_CONFIG.links.appointment} className={styles.primaryCta}>
                <FiCalendar aria-hidden="true" />
                קביעת פגישת ייעוץ
              </Link>
              <a href="#services" className={styles.secondaryCta}>
                למצוא את הליווי המתאים
                <FiChevronDown aria-hidden="true" />
              </a>
            </div>
            <div className={styles.trustRow} aria-label="פרטי השירות">
              <span><FiMapPin aria-hidden="true" /> אשדוד</span>
              <span><FiMonitor aria-hidden="true" /> אונליין</span>
              <span><FiShield aria-hidden="true" /> מרחב אישי ומכבד</span>
            </div>
          </div>

          <div className={styles.heroVisual}>
            <div className={styles.imageFrame}>
              <img
                src="/images/shira-saharoni.webp"
                alt="שירה סהרוני, יועצת זוגית, מנחת הורים ומגשרת"
                width="1271"
                height="1280"
                fetchPriority="high"
              />
              <div className={styles.imageWash} />
            </div>
            <div className={styles.glassNote}>
              <span className={styles.noteIcon}><FiMessageCircle aria-hidden="true" /></span>
              <p>
                <strong>לפעמים שינוי מתחיל</strong>
                משיחה אחת שבה באמת מצליחים לראות מה קורה.
              </p>
            </div>
            <div className={styles.roleCard}>
              <span>עורכת דין בהכשרתה</span>
              <strong>מגשרת מוסמכת</strong>
            </div>
          </div>
        </section>

        <section className={styles.signalBar} aria-label="תחומי העיסוק של שירה">
          <span>ייעוץ זוגי</span>
          <i aria-hidden="true" />
          <span>הנחיית הורים</span>
          <i aria-hidden="true" />
          <span>גישור</span>
          <i aria-hidden="true" />
          <span>ליווי בתקופות מעבר</span>
        </section>

        <section id="services" className={`${styles.section} ${styles.servicesSection}`}>
          <div className={styles.sectionHeading}>
            <span className={styles.kicker}>איך אוכל לעזור</span>
            <h2>מקום לעשות בו סדר,<br />בלי לפשט את מה שמורכב.</h2>
            <p>אפשר להתחיל מהנושא שהכי מעסיק אתכם עכשיו. את החיבורים בין הדברים נבין יחד.</p>
          </div>

          <div className={styles.serviceGrid}>
            {services.map(({ title, description, link, icon: Icon, accent }, index) => (
              <Link
                to={link}
                className={`${styles.serviceCard} ${styles[accent]}`}
                key={title}
                style={{ '--delay': `${index * 90}ms` } as React.CSSProperties}
              >
                <span className={styles.serviceIcon}><Icon aria-hidden="true" /></span>
                <span className={styles.serviceIndex}>0{index + 1}</span>
                <h3>{title}</h3>
                <p>{description}</p>
                <span className={styles.cardLink}>
                  לקריאה נוספת
                  <FiArrowLeft aria-hidden="true" />
                </span>
              </Link>
            ))}
          </div>
        </section>

        <section id="about" className={`${styles.section} ${styles.aboutSection}`}>
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
              <p>המטרה היא לא לדבר מושלם — אלא להצליח להקשיב, להבין ולבחור תגובה אחרת.</p>
            </div>
          </div>

          <div className={styles.aboutCopy}>
            <span className={styles.kicker}>נעים מאוד, שירה</span>
            <h2>מקצועיות שמחזיקה את המורכבות. שיחה שנשארת אנושית.</h2>
            <p className={styles.aboutLead}>
              אני עורכת דין בהכשרתי ומגשרת מוסמכת, שבחרה לעבור מעולם המשפט
              לעולמות ההנחיה, הייעוץ והחינוך.
            </p>
            <p>
              אני אוהבת לפרק יחד מצב שנראה מסובך: להבין מי נפגע, מה חוזר על עצמו
              ומה אפשר לנסות אחרת כבר השבוע.
            </p>
            <ul className={styles.focusList}>
              {focusAreas.map((area) => (
                <li key={area}><FiCheck aria-hidden="true" />{area}</li>
              ))}
            </ul>
            <Link to="/about" className={styles.textLink}>
              עוד עליי ועל אופן העבודה
              <FiArrowLeft aria-hidden="true" />
            </Link>
          </div>
        </section>

        <section id="process" className={`${styles.section} ${styles.processSection}`}>
          <div className={styles.sectionHeading}>
            <span className={styles.kicker}>איך מתחילים</span>
            <h2>בהירות לפני הכול.</h2>
            <p>לא צריך להגיע עם ניסוח מדויק. מתחילים ממה שקשה עכשיו ומתקדמים צעד אחר צעד.</p>
          </div>
          <div className={styles.processGrid}>
            {process.map((step) => (
              <article className={styles.processCard} key={step.number}>
                <span className={styles.processNumber}>{step.number}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className={styles.testimonialSection}>
          <div className={styles.testimonialGlow} aria-hidden="true" />
          <FiStar className={styles.starIcon} aria-hidden="true" />
          <blockquote>
            “הגענו לשירה בשיא המשבר. היא עזרה לנו להוריד את גובה הלהבות
            ולדבר בפעם הראשונה מזה שנים.”
          </blockquote>
          <p>א׳ ו־מ׳, אשדוד <span>הפרטים המזהים הושמטו לשמירה על פרטיות הפונים</span></p>
        </section>

        <section className={styles.finalCta}>
          <div>
            <span className={styles.kicker}>אפשר להתחיל מכאן</span>
            <h2>השיחה הראשונה לא חייבת לפתור הכול.<br />היא רק צריכה לפתוח דרך.</h2>
          </div>
          <div className={styles.finalActions}>
            <Link to={SITE_CONFIG.links.appointment} className={styles.lightCta}>
              <FiCalendar aria-hidden="true" />
              קביעת פגישה
            </Link>
            <a href={SITE_CONFIG.links.whatsapp} className={styles.whatsappCta}>
              <FiMessageCircle aria-hidden="true" />
              כתבו לי ב־WhatsApp
            </a>
          </div>
        </section>
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerBrand}>
          <span className={styles.brandMark}>ש</span>
          <div>
            <strong>שירה סהרוני</strong>
            <small>ייעוץ זוגי · הנחיית הורים · גישור</small>
          </div>
        </div>
        <div className={styles.footerLinks}>
          <Link to="/privacy">פרטיות</Link>
          <Link to="/accessibility">נגישות</Link>
          <Link to="/">לאתר הנוכחי</Link>
        </div>
        <span className={styles.footerBeta}>גרסת BETA ניסיונית</span>
      </footer>
    </div>
  );
};

export default BetaPage;
