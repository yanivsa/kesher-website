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
  FiUsers,
  FiX,
} from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import SignatureMark from '../../components/Signature/SignatureMark';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './Home.module.css';

const schemaData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "LocalBusiness",
      "@id": `${SITE_CONFIG.url}/#business`,
      "name": SITE_CONFIG.author,
      "alternateName": "Shira Saharoni",
      "url": SITE_CONFIG.url,
      "telephone": SITE_CONFIG.contact.phone,
      "description": SITE_CONFIG.description,
      "areaServed": [
        {
          "@type": "City",
          "name": "אשדוד"
        },
        {
          "@type": "Country",
          "name": "ישראל"
        }
      ],
      "availableLanguage": "he",
      "address": {
        "@type": "PostalAddress",
        "addressLocality": "אשדוד",
        "addressCountry": "IL"
      },
      "knowsAbout": [
        "ייעוץ זוגי",
        "הדרכת הורים",
        "גישור",
        "ילדים מחוננים",
        "הכנה למסגרת מחוננים",
        "משפחות עולים",
        "תושבים חוזרים",
        "זוגיות ברילוקיישן",
        "הכנה לנישואים",
        "השנה הראשונה לנישואים",
        "רווקות מאוחרת",
        "מציאת זוגיות",
        "דייטים",
        "ADHD",
        "תקשורת בזוגיות",
        "הורות משותפת"
      ],
      "makesOffer": [
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "הכנה לנישואים וליווי בשנה הראשונה",
            "url": `${SITE_CONFIG.url}/services/premarital-first-year`,
            "description": "פגישות הכנה זוגיות סביב כסף, בית, משפחות, אינטימיות, חלוקת אחריות ותקשורת."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "ייעוץ זוגי לעולים ולזוגות ברילוקיישן",
            "url": `${SITE_CONFIG.url}/services/couples-aliyah-relocation`,
            "description": "ייעוץ זוגי לפני מעבר מדינה, בתקופת ההסתגלות ולאחר החזרה."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "ייעוץ במצבי רווקות מאוחרת",
            "url": `${SITE_CONFIG.url}/services/late-singleness`,
            "description": "ייעוץ אישי סביב שחיקה, לחץ מהסביבה, בדידות ודפוסים חוזרים."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "ליווי למציאת זוגיות",
            "url": `${SITE_CONFIG.url}/services/finding-relationship`,
            "description": "ליווי אישי סביב היכרויות, בחירת קשר, תקשורת, גבולות ובניית קשר."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "ייעוץ זוגי",
            "url": `${SITE_CONFIG.url}/services/couples`,
            "description": "ייעוץ זוגי לשיפור תקשורת, התמודדות עם משברים וחיזוק הקשר."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "הדרכת הורים",
            "url": `${SITE_CONFIG.url}/services/parenting`,
            "description": "הדרכה להורים לילדים מחוננים ולילדים עם ADHD, כולל מעברים חינוכיים ותפקודים ניהוליים."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "גישור",
            "url": `${SITE_CONFIG.url}/services/mediation`,
            "description": "גישור לבני זוג, משפחות, הורים, שכנים ושותפים לצורך בניית הסכמות מעשיות."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "הנחיית הורים לילדים מחוננים",
            "url": `${SITE_CONFIG.url}/services/gifted-parenting`,
            "description": "הנחיית הורים סביב מחוננות, רגישות, שייכות, תפקודים ניהוליים והכנה למסגרת מחוננים."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "ליווי משפחות עולים ותושבים חוזרים",
            "url": `${SITE_CONFIG.url}/services/aliyah-families`,
            "description": "ייעוץ זוגי והנחיית הורים למשפחות בתקופת עלייה לישראל או חזרה אליה."
          }
        }
      ],
      "image": `${SITE_CONFIG.url}/images/generated/site/home-hero.jpg`,
      "priceRange": "$$",
      "potentialAction": {
        "@type": "ReserveAction",
        "target": {
          "@type": "EntryPoint",
          "urlTemplate": `${SITE_CONFIG.url}/appointment`,
          "inLanguage": "he"
        }
      }
    },
    {
      "@type": "WebSite",
      "@id": `${SITE_CONFIG.url}/#website`,
      "url": SITE_CONFIG.url,
      "name": SITE_CONFIG.title,
      "description": SITE_CONFIG.description,
      "publisher": {
        "@id": `${SITE_CONFIG.url}/#business`
      },
      "inLanguage": "he"
    },
    {
      "@type": "Person",
      "@id": `${SITE_CONFIG.url}/#shira`,
      "name": SITE_CONFIG.author,
      "alternateName": "Shira Saharoni",
      "url": `${SITE_CONFIG.url}/about`,
      "image": `${SITE_CONFIG.url}/images/shira-saharoni.webp`,
      "jobTitle": [
        "יועצת זוגית",
        "מנחת הורים",
        "מגשרת מוסמכת"
      ],
      "worksFor": {
        "@id": `${SITE_CONFIG.url}/#business`
      },
      "knowsAbout": [
        "ייעוץ זוגי",
        "הנחיית הורים",
        "גישור",
        "ילדים מחוננים",
        "תפקודים ניהוליים",
        "משפחות עולים ותושבים חוזרים",
        "זוגיות בעלייה וברילוקיישן",
        "הכנה לנישואים והשנה הראשונה",
        "רווקות מאוחרת",
        "מציאת זוגיות"
      ]
    },
    {
      "@type": "BreadcrumbList",
      "itemListElement": [
        {
          "@type": "ListItem",
          "position": 1,
          "name": "עמוד הבית",
          "item": SITE_CONFIG.url
        }
      ]
    }
  ]
};

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
  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'touch') return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width;
    const y = (event.clientY - bounds.top) / bounds.height;
    event.currentTarget.style.setProperty('--tilt-x', `${(0.5 - y) * 5}deg`);
    event.currentTarget.style.setProperty('--tilt-y', `${(x - 0.5) * 7}deg`);
    event.currentTarget.style.setProperty('--glow-x', `${x * 100}%`);
    event.currentTarget.style.setProperty('--glow-y', `${y * 100}%`);
  };

  const resetTilt = (event: React.PointerEvent<HTMLDivElement>) => {
    event.currentTarget.style.removeProperty('--tilt-x');
    event.currentTarget.style.removeProperty('--tilt-y');
    event.currentTarget.style.removeProperty('--glow-x');
    event.currentTarget.style.removeProperty('--glow-y');
  };

  return (
    <div className={styles.heroVisualStage}>
      <div
        className={styles.heroVisual}
        onPointerMove={handlePointerMove}
        onPointerLeave={resetTilt}
      >
        <div className={styles.imageFrame}>
          <img
            src="/images/shira-saharoni.webp"
            alt="שירה סהרוני, יועצת זוגית, מנחת הורים ומגשרת"
            width="477"
            height="1024"
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
      </div>
      <span className={styles.visualHalo} aria-hidden="true" />
    </div>
  );
};

const Home: React.FC = () => {
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
        title={`${SITE_CONFIG.author} — ייעוץ זוגי, הנחיית הורים וגישור באשדוד`}
        description={SITE_CONFIG.description}
      />
      <SchemaOrg data={schemaData} />
      <ScrollProgress />

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

          <nav className={styles.desktopNav} aria-label="ניווט ראשי">
            <a href="#services">איך אוכל לעזור</a>
            <a href="#about">אודות</a>
            <a href="#process">איך זה עובד</a>
            <Link to="/blog">מאמרים</Link>
          </nav>

          <div className={styles.headerActions}>
            <Link to={SITE_CONFIG.links.appointment} className={styles.headerCta}>
              קביעת פגישה
              <FiArrowLeft aria-hidden="true" />
            </Link>
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
              אפשר לבחור לבנות
              <span> את הקשר אחרת. יחד.</span>
            </h1>
            <p className={styles.heroLead}>
              גם כשהשיחות נתקעות והעומס גדל, אפשר להבין מה קורה בזוגיות או בבית,
              לבחור צעדים חדשים וליצור תנועה שמחזירה תקווה לקשר ולמשפחה.
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
            <a href={SITE_CONFIG.links.whatsapp} className={styles.heroWhatsapp}>
              <FiMessageCircle aria-hidden="true" />
              מעדיפים להתחיל בהודעה? כתבו לי ב־WhatsApp
              <FiArrowLeft aria-hidden="true" />
            </a>
            <div className={styles.trustRow} aria-label="פרטי השירות">
              <span><FiMapPin aria-hidden="true" /> אשדוד</span>
              <span><FiMonitor aria-hidden="true" /> אונליין</span>
              <span><FiShield aria-hidden="true" /> מרחב אישי ומכבד</span>
            </div>
          </div>

          <InteractiveHeroVisual />
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

        <section id="services" className={`${styles.section} ${styles.revealSection}`}>
          <div className={styles.sectionHeading}>
            <span className={styles.kicker}>לא צריך לדעת מראש מה הכותרת המדויקת לקושי.</span>
            <h2>מתחילים מהמקום שבו<br />הקשר מבקש שינוי.</h2>
            <p>אפשר להתחיל מהנושא שהכי מעסיק אתכם עכשיו. את החיבורים בין הדברים נבין יחד.</p>
          </div>

          <div className={styles.serviceGrid}>
            {services.map(({ title, description, link, icon: Icon, accent, tags }, index) => (
              <Link
                to={link}
                className={`${styles.serviceCard} ${styles[accent]} ${index < 2 ? styles.primaryService : styles.secondaryService}`}
                key={title}
                style={{ '--delay': `${index * 90}ms` } as React.CSSProperties}
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
              </Link>
            ))}
          </div>
        </section>

        <section className={`${styles.section} ${styles.trustSection} ${styles.revealSection}`}>
          <div className={styles.trustHeading}>
            <span className={styles.kicker}>אמון נבנה בחוויה</span>
            <h2>מה משתנה כשמצליחים לדבר אחרת.</h2>
            <p>הפרטים המזהים הושמטו כדי לשמור על פרטיות הפונים.</p>
          </div>
          <div className={styles.quoteGrid}>
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
          </div>
        </section>

        <section id="about" className={`${styles.section} ${styles.aboutSection} ${styles.revealSection}`}>
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
              <p><strong>יש דרך לדבר.</strong><br />גם כשכבר קשה לשמוע.</p>
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
            <SignatureMark tone="homeAbout" animated className={styles.aboutSignature} />
            <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
              <Link to="/about" className={styles.textLink}>
                עוד עליי ועל אופן העבודה
                <FiArrowLeft aria-hidden="true" />
              </Link>
              <Link to="/lectures" className={styles.textLink}>
                צפו בהרצאות ובסדנאות
                <FiArrowLeft aria-hidden="true" />
              </Link>
            </div>
            <p className={styles.legalBackground}>רקע נוסף: עורכת דין בהכשרתי.</p>
          </div>
        </section>

        <section id="process" className={`${styles.section} ${styles.processSection} ${styles.revealSection}`}>
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
        </section>


        <section id="faq" className={`${styles.section} ${styles.faqSection} ${styles.revealSection}`}>
          <div className={styles.sectionHeading}>
            <span className={styles.kicker}>שאלות נפוצות</span>
            <h2>מידע נוסף שכדאי לדעת.</h2>
            <p>אם השאלה שלכם לא מופיעה כאן, אפשר תמיד לפנות אליי ישירות לבירור.</p>
          </div>
          <div className={styles.faqGrid}>
            <article className={styles.faqCard}>
              <h3 className={styles.faqQuestion}>האם ייעוץ זוגי מתאים רק לזוגות במשבר?</h3>
              <p className={styles.faqAnswer}>לא. גם זוגות שרוצים לחזק את הקשר, לשפר את התקשורת ביניהם או לעבור יחד תקופה מאתגרת, מוזמנים להגיע. המפגשים יכולים להעניק כלים נוספים להתמודדות משותפת עם השגרה והאתגרים.</p>
            </article>
            <article className={styles.faqCard}>
              <h3 className={styles.faqQuestion}>האם הדרכת הורים מתקיימת עם הילדים?</h3>
              <p className={styles.faqAnswer}>בדרך כלל ההדרכה מיועדת להורים בלבד. אנו מתמקדים במתן כלים, הבנה וביטחון להורים כדי לסייע להם להתמודד עם המצבים השונים שעולים בבית. במקרים מסוימים ולפי הצורך, ניתן לשלב מפגש משותף.</p>
            </article>
            <article className={styles.faqCard}>
              <h3 className={styles.faqQuestion}>האם ניתן לקיים פגישות מרחוק (אונליין)?</h3>
              <p className={styles.faqAnswer}>כן. חלק מהפגישות יכולות להתקיים באונליין, בהתאם לנוחות ולהעדפה שלכם. ניתן לשלב בין מפגשים בקליניקה למפגשים מקוונים.</p>
            </article>
          </div>
        </section>

        <section className={`${styles.finalCta} ${styles.revealSection}`}>
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

      <aside className={styles.quickDock} aria-label="אפשרויות ליצירת קשר">
        <span className={styles.quickDockLabel}>אפשר להתחיל בדרך שנוחה לכם</span>
        <Link to={SITE_CONFIG.links.appointment}>
          <FiCalendar aria-hidden="true" />
          <span>פגישה</span>
        </Link>
        <a href={SITE_CONFIG.links.whatsapp}>
          <FiMessageCircle aria-hidden="true" />
          <span>WhatsApp</span>
        </a>
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
          <Link to="/contact">יצירת קשר</Link>
          <Link to="/blog">מאמרים</Link>
          <Link to="/privacy">פרטיות</Link>
          <Link to="/accessibility">נגישות</Link>
        </div>
      </footer>
    </div>
  );
};

export default Home;