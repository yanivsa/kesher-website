export default {
  async fetch(request, env, ctx) {
    // Forward the request to the origin
    const response = await fetch(request);
    const contentType = response.headers.get("content-type");

    // Only apply HTMLRewriter to HTML responses
    if (contentType && contentType.includes("text/html")) {
      const city = request.cf?.city || "";
      const requestUrl = new URL(request.url);
      const canonicalUrl = `https://kesher.saharoni.com${requestUrl.pathname}`;
      
      // JSON-LD Schema for Therapist / LocalBusiness
      const jsonLd = {
        "@context": "https://schema.org",
        "@type": "Therapist",
        "name": "שירה סהרוני — ייעוץ זוגי, הדרכת הורים וגישור",
        "url": "https://kesher.saharoni.com",
        "telephone": "+972-50-2763802",
        "address": {
          "@type": "PostalAddress",
          "addressLocality": "אשדוד",
          "addressCountry": "IL"
        },
        "serviceType": ["ייעוץ זוגי", "הדרכת הורים", "גישור משפחתי"],
        "description": "יועצת זוגית ומגשרת מוסמכת באשדוד עם ניסיון בהדרכת הורים לילדים עם ADHD"
      };

      class HeadRewriter {
        constructor(canonical) {
          this.canonical = canonical;
        }
        element(element) {
          // Inject JSON-LD
          element.append(`<script type="application/ld+json">${JSON.stringify(jsonLd)}</script>`, { html: true });
          
          // Inject OG Tags
          element.append(`<meta property="og:type" content="website" />`, { html: true });
          element.append(`<meta property="og:title" content="שירה סהרוני | ייעוץ זוגי, הדרכת הורים וגישור" />`, { html: true });
          element.append(`<meta property="og:description" content="יועצת זוגית ומנחת הורים מוסמכת באשדוד. מציעה ייעוץ זוגי, הדרכת הורים וגישור." />`, { html: true });
          element.append(`<meta property="og:url" content="${this.canonical}" />`, { html: true });
          element.append(`<meta property="og:site_name" content="שירה סהרוני" />`, { html: true });
          
          // Inject Canonical Tag
          element.append(`<link rel="canonical" href="${this.canonical}" />`, { html: true });
        }
      }

      class TitleRewriter {
        element(element) {
          // Geo customization if user is in Ashdod
          if (city === "Ashdod") {
            element.prepend("קרוב אליך באשדוד | ", { html: true });
          }
        }
      }

      // Clone response to modify headers
      let newResponse = new Response(response.body, response);
      
      // Add Cache-Control for Core Web Vitals (LCP)
      newResponse.headers.set('Cache-Control', 'public, max-age=3600, s-maxage=86400');

      // Transform HTML
      return new HTMLRewriter()
        .on("head", new HeadRewriter(canonicalUrl))
        .on("title", new TitleRewriter())
        .transform(newResponse);
    }

    return response;
  }
};