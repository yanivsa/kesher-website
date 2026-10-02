interface Env {
  KESHER_MCP: Fetcher;
}

export const onRequest: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.KESHER_MCP) {
    return new Response('Kesher MCP service binding is unavailable', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }

  return env.KESHER_MCP.fetch(request);
};
