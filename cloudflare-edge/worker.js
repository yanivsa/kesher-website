export default {
  async fetch(request, env, ctx) {
    // Forward the request to the origin
    const response = await fetch(request);
    const contentType = response.headers.get("content-type");

    // Only apply HTMLRewriter to HTML responses
    if (contentType && contentType.includes("text/html")) {
      const city = request.cf?.city || "";
      const requestUrl = new URL(request.url);

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
        .on("title", new TitleRewriter())
        .transform(newResponse);
    }

    return response;
  }
};