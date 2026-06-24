// Cloudflare Pages Function — www → apex 301 redirect
// Path: /functions/[[path]].js
// Handles all routes (assets included) and only redirects when host starts with "www."

export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);

  // Canonical host (apex) — no www, no scheme
  const APEX = "curated.my.id";

  // Detect www subdomain
  if (url.hostname.toLowerCase() === `www.${APEX}`) {
    // Preserve path, query, and fragment
    const target = new URL(request.url);
    target.hostname = APEX;
    // HTTPS forced (Cloudflare Pages already serves HTTPS, but be explicit)
    target.protocol = "https:";
    // Drop default port if any
    target.port = "";

    return new Response(null, {
      status: 301,
      statusText: "Moved Permanently",
      headers: {
        Location: target.toString(),
        // Hint for downstream caches
        "Cache-Control": "public, max-age=3600",
      },
    });
  }

  // Otherwise, pass through to the static asset / next function
  return context.next();
}
