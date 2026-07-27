import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FiArrowLeft,
  FiArrowUpLeft,
  FiCalendar,
  FiCheck,
  FiMapPin,
  FiMenu,
  FiMessageCircle,
  FiMonitor,
  FiX,
} from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './BetaPage.module.css';

const services = [
  {
    number: '01',
    title: 'ייעוץ זוגי',
    description: 'כשהשיחות מסתיימות שוב באותו מקום, נלמד לזהות את הדפוס וליצור דרך חדשה להיפגש.',
    prompt: 'תקשורת · קרבה · אמון',
    link: '/services/couples',
  },
  {
    number: '02',
    title: 'הדרכת הורים',
    description: 'גבולות ושגרה שנשענים על הבנה וקשר — גם בתקופות עמוסות, רגישות ומבלבלות.',
    prompt: 'גבולות · ויסות · שגרה',
    link: '/services/parenting',
  },
  {
    number: '03',
    title: 'גישור',
    description: 'מרחב ענייני לניהול מחלוקת, הפחתת המתח וניסוח הסכמות שאפשר באמת לקיים.',
    prompt: 'הקשבה · בהירות · הסכמות',
    link: '/services/mediation',
  },
];

const process = [
  {
    number: 'א',
    title: 'מתחילים במה שכואב עכשיו',
    text: 'לא צריך להגיע עם אבחנה או ניסוח מדויק. מתחילים מהרגעים שבהם הקשר נתקע.',
  },
  {
    number: 'ב',
    title: 'רואים את התמונה המלאה',
    text: 'מבינים מה מפעיל אתכם, מה חוזר על עצמו ואילו צרכים נשארים בלי מענה.',
  },
  {
    number: 'ג',
    title: 'מתרגלים תנועה חדשה',
    text: 'יוצאים עם כיוון ברור וכלים שאפשר לקחת לחיים שמחוץ לחדר.',
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

const focusAreas = [
  'זוגיות בתקופות של ריחוק ושחיקה',
  'הורות לילדים מחוננים וילדים עם ADHD',
  'הכנה לנישואים והשנה הראשונה',
  'משפחות בעלייה, בחזרה לישראל וברילוקיישן',
];

const navItems = [
  { label: 'תחומי ליווי', href: '#services' },
  { label: 'הגישה', href: '#approach' },
  { label: 'אודות', href: '#about' },
  { label: 'איך מתחילים', href: '#process' },
];

const EditorialPortrait = () => {
  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'touch') return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width;
    const y = (event.clientY - bounds.top) / bounds.height;
    event.currentTarget.style.setProperty('--portrait-x', `${(x - 0.5) * 8}px`);
    event.currentTarget.style.setProperty('--portrait-y', `${(y - 0.5) * 8}px`);
  };

  const resetPortrait = (event: React.PointerEvent<HTMLDivElement>) => {
    event.currentTarget.style.removeProperty('--portrait-x');
    event.currentTarget.style.removeProperty('--portrait-y');
  };

  return (
    <div
      className={styles.portraitPanel}
      onPointerMove={handlePointerMove}
      onPointerLeave={resetPortrait}
    >
      <div className={styles.portraitCurtain} aria-hidden="true" />
      <img
        src="/images/shira-saharoni.webp"
        alt="שירה סהרוני, יועצת זוגית, מנחת הורים ומגשרת"
        width="1271"
        height="1280"
        fetchPriority="high"
      />
      <div className={styles.portraitWash} aria-hidden="true" />
      <div className={styles.portraitCaption}>
        <span>שירה סהרוני</span>
        <strong>ייעוץ זוגי · הדרכת הורים · גישור</strong>
      </div>
      <div className={styles.portraitIndex} aria-hidden="true">03</div>
    </div>
  );
};

const BetaPage: React.FC = () => {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
        requestAnimationFrame(() => menuButtonRef.current?.focus());
      }
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [menuOpen]);

  const closeMenu = () => setMenuOpen(false);

  return (
    <div className={styles.page} dir="rtl">
      <MetaTags
        title="Beta 3 — שירה סהרוני"
        description="גרסת Beta 3 הניסיונית של שירה סהרוני — ייעוץ זוגי, הדרכת הורים וגישור באשדוד ובאונליין."
        canonical={`${SITE_CONFIG.url}/b`}
        image="/images/shira-saharoni.webp"
        noIndex
      />

      <div className={styles.scrollProgress} aria-hidden="true" />

      <header className={styles.header}>
        <a href="#top" className={styles.brand} aria-label="שירה סהרוני — לראש העמוד">
          <span className={styles.brandName}>שירה סהרוני</span>
          <span className={styles.brandRole}>ייעוץ · הורות · גישור</span>
        </a>

        <nav className={styles.desktopNav} aria-label="ניווט בגרסת Beta 3">
          {navItems.map((item) => <a href={item.href} key={item.href}>{item.label}</a>)}
          <Link to="/blog">מאמרים</Link>
        </nav>

        <div className={styles.headerActions}>
          <span className={styles.betaBadge}>BETA 3</span>
          <Link to={SITE_CONFIG.links.appointment} className={styles.headerCta}>
            לקביעת פגישה
            <FiArrowLeft aria-hidden="true" />
          </Link>
          <button
            ref={menuButtonRef}
            type="button"
            className={styles.menuButton}
            aria-label={menuOpen ? 'סגירת תפריט' : 'פתיחת תפריט'}
            aria-expanded={menuOpen}
            aria-controls="beta3-mobile-menu"
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <FiX aria-hidden="true" /> : <FiMenu aria-hidden="true" />}
          </button>
        </div>

        {menuOpen && (
          <div className={styles.mobileMenuShell}>
            <button
              type="button"
              className={styles.menuBackdrop}
              aria-label="סגירת התפריט בלחיצה מחוץ לתפריט"
              onClick={closeMenu}
            />
            <nav id="beta3-mobile-menu" className={styles.mobileNav} aria-label="ניווט Beta 3 למובייל">
              <div className={styles.mobileNavHeading}>
                <span>BETA 3</span>
                <small>תפריט</small>
              </div>
              {navItems.map((item, index) => (
                <a href={item.href} onClick={closeMenu} key={item.href}>
                  <span>0{index + 1}</span>
                  {item.label}
                </a>
              ))}
              <Link to="/blog" onClick={closeMenu}>
                <span>05</span>
                מאמרים
              </Link>
              <Link to={SITE_CONFIG.links.appointment} className={styles.mobileAppointment} onClick={closeMenu}>
                לקביעת פגישה
                <FiArrowLeft aria-hidden="true" />
              </Link>
            </nav>
          </div>
        )}
      </header>

      <main id="main-content">
        <section id="top" className={styles.hero}>
          <div className={styles.heroCopy}>
            <div className={styles.heroMeta}>
              <span><FiMapPin aria-hidden="true" /> אשדוד</span>
              <span><FiMonitor aria-hidden="true" /> אונליין</span>
            </div>
            <div className={styles.heroLabel}>
              <span>מרחב מקצועי לקשרים אנושיים</span>
              <i aria-hidden="true" />
            </div>
            <h1>
              <span>יש דרך לדבר.</span>
              <span className={styles.outlineLine}>גם כשכבר קשה</span>
              <span>לשמוע.</span>
            </h1>
            <p className={styles.heroLead}>
              ייעוץ זוגי, הדרכת הורים וגישור בגישה רגישה ומעשית —
              כדי להבין מה קורה ביניכם וליצור תנועה שאפשר להרגיש בחיים עצמם.
            </p>
            <div className={styles.heroActions}>
              <Link to={SITE_CONFIG.links.appointment} className={styles.primaryCta}>
                <FiCalendar aria-hidden="true" />
                תיאום פגישת ייעוץ
                <FiArrowUpLeft aria-hidden="true" />
              </Link>
              <a href={SITE_CONFIG.links.whatsapp} className={styles.textCta}>
                מתחילים בהודעה
                <FiMessageCircle aria-hidden="true" />
              </a>
            </div>
            <div className={styles.heroEdition}>
              <span>03</span>
              <p><strong>גרסת ניסוי</strong> עיצוב חדש לבחינת האתר העתידי</p>
            </div>
          </div>

          <EditorialPortrait />
        </section>

        <section className={styles.credentialBar} aria-label="פרטים מקצועיים">
          <div><span>01</span><strong>עורכת דין בהכשרתה</strong></div>
          <div><span>02</span><strong>מגשרת מוסמכת</strong></div>
          <div><span>03</span><strong>פגישות באשדוד ובאונליין</strong></div>
          <div><span>04</span><strong>מרחב דיסקרטי ומכבד</strong></div>
        </section>

        <section id="services" className={`${styles.services} ${styles.reveal}`}>
          <div className={styles.sectionIntro}>
            <span className={styles.sectionNumber}>01 / תחומי ליווי</span>
            <div>
              <p className={styles.kicker}>לא צריך לדעת מראש מה הכותרת המדויקת לקושי.</p>
              <h2>מתחילים מהמקום שבו הקשר מבקש שינוי.</h2>
            </div>
          </div>

          <div className={styles.serviceList}>
            {services.map((service) => (
              <Link to={service.link} className={styles.serviceRow} key={service.number}>
                <span className={styles.serviceNumber}>{service.number}</span>
                <div className={styles.serviceTitle}>
                  <h3>{service.title}</h3>
                  <span>{service.prompt}</span>
                </div>
                <p>{service.description}</p>
                <span className={styles.serviceArrow} aria-hidden="true"><FiArrowUpLeft /></span>
              </Link>
            ))}
          </div>
        </section>

        <section id="approach" className={`${styles.approach} ${styles.reveal}`}>
          <div className={styles.approachImage}>
            <img
              src="/images/generated/site/home-hero.jpg"
              alt="חדר הייעוץ של שירה סהרוני באשדוד"
              width="1600"
              height="900"
              loading="lazy"
            />
            <span>החדר באשדוד</span>
          </div>
          <div className={styles.approachCopy}>
            <span className={styles.sectionNumber}>02 / הגישה</span>
            <blockquote>
              לא צריך לדבר מושלם.
              <em>צריך להרגיש שמישהו באמת מקשיב.</em>
            </blockquote>
            <p>
              בתוך קושי זוגי או משפחתי קל להישאב לשאלה מי צודק. העבודה המשותפת
              מחזירה אותנו לשאלות שעוזרות לזוז: מה קורה כאן, מה כל אחד צריך,
              ואיזו תגובה חדשה אפשר לנסות כבר השבוע.
            </p>
            <div className={styles.approachPrinciples}>
              <span>בהירות לפני עצות</span>
              <span>כלים בתוך הקשר</span>
              <span>קצב שמתאים לכם</span>
            </div>
          </div>
        </section>

        <section className={`${styles.testimonials} ${styles.reveal}`} aria-labelledby="testimonials-title">
          <div className={styles.testimonialLead}>
            <span className={styles.sectionNumber}>03 / מילים מהחדר</span>
            <h2 id="testimonials-title">כשמשהו בשיחה מתחיל להשתנות.</h2>
            <p>הפרטים המזהים הושמטו כדי לשמור על פרטיות הפונים.</p>
          </div>
          <div className={styles.quoteEditorial}>
            <blockquote>
              <span className={styles.quoteMark} aria-hidden="true">״</span>
              <p>“{testimonials[0].text}”</p>
              <footer>
                <strong>{testimonials[0].author}</strong>
                <span>{testimonials[0].type}</span>
              </footer>
            </blockquote>
            <div className={styles.smallQuotes}>
              {testimonials.slice(1).map((testimonial) => (
                <blockquote key={testimonial.author}>
                  <p>“{testimonial.text}”</p>
                  <footer>
                    <strong>{testimonial.author}</strong>
                    <span>{testimonial.type}</span>
                  </footer>
                </blockquote>
              ))}
            </div>
          </div>
        </section>

        <section id="about" className={`${styles.about} ${styles.reveal}`}>
          <div className={styles.aboutStatement}>
            <span className={styles.sectionNumber}>04 / אודות</span>
            <h2>מקצועיות שמחזיקה מורכבות. שיחה שנשארת אנושית.</h2>
            <Link to="/about" className={styles.editorialLink}>
              עוד עליי ועל אופן העבודה
              <FiArrowLeft aria-hidden="true" />
            </Link>
          </div>
          <div className={styles.aboutBody}>
            <p className={styles.aboutLead}>
              אני שירה סהרוני, עורכת דין בהכשרתי ומגשרת מוסמכת. בחרתי לעבור
              מעולם המשפט לעולמות הייעוץ, ההנחיה והחינוך.
            </p>
            <p>
              אני אוהבת לפרק יחד מצב שנראה מסובך: להבין מי נפגע, מה חוזר על עצמו,
              ומה אפשר לנסות אחרת — בלי למחוק את המורכבות ובלי להישאר תקועים בתוכה.
            </p>
            <ul>
              {focusAreas.map((area) => (
                <li key={area}><FiCheck aria-hidden="true" />{area}</li>
              ))}
            </ul>
          </div>
        </section>

        <section id="process" className={`${styles.process} ${styles.reveal}`}>
          <div className={styles.processHeading}>
            <span className={styles.sectionNumber}>05 / איך מתחילים</span>
            <h2>שלושה צעדים. בלי הצגות, בלי הבטחות גדולות.</h2>
          </div>
          <div className={styles.processGrid}>
            {process.map((step) => (
              <article key={step.number}>
                <span>{step.number}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className={styles.finalCta}>
          <div className={styles.finalIndex} aria-hidden="true">03</div>
          <span className={styles.sectionNumber}>אפשר להתחיל מכאן</span>
          <h2>השיחה הראשונה לא צריכה לפתור הכול.<br />רק לפתוח דרך.</h2>
          <div className={styles.finalActions}>
            <Link to={SITE_CONFIG.links.appointment}>
              <FiCalendar aria-hidden="true" />
              קביעת פגישה
              <FiArrowUpLeft aria-hidden="true" />
            </Link>
            <a href={SITE_CONFIG.links.whatsapp}>
              <FiMessageCircle aria-hidden="true" />
              כתבו לי ב־WhatsApp
            </a>
          </div>
        </section>
      </main>

      <aside className={styles.quickConnect} aria-label="אפשרויות ליצירת קשר">
        <span>BETA 3</span>
        <Link to={SITE_CONFIG.links.appointment}>
          <FiCalendar aria-hidden="true" />
          פגישה
        </Link>
        <a href={SITE_CONFIG.links.whatsapp}>
          <FiMessageCircle aria-hidden="true" />
          WhatsApp
        </a>
      </aside>

      <footer className={styles.footer}>
        <div>
          <strong>שירה סהרוני</strong>
          <span>ייעוץ זוגי · הדרכת הורים · גישור</span>
        </div>
        <nav aria-label="קישורים משלימים">
          <Link to="/privacy">פרטיות</Link>
          <Link to="/accessibility">נגישות</Link>
          <Link to="/">לאתר הנוכחי</Link>
        </nav>
        <span className={styles.footerEdition}>BETA 3 / ניסוי עיצובי</span>
      </footer>
    </div>
  );
};

export default BetaPage;
