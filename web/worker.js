/**
 * Worker tipis: semua request dilayani dari aset statis PWA.
 * Service worker dan manifest tidak boleh di-cache lama, supaya update
 * langsung terpakai oleh browser yang sudah memasang aplikasinya.
 */
export default {
  async fetch(request, env) {
    const response = await env.ASSETS.fetch(request);
    const { pathname } = new URL(request.url);
    if (pathname === "/sw.js" || pathname === "/manifest.webmanifest") {
      const headers = new Headers(response.headers);
      headers.set("cache-control", "no-cache");
      return new Response(response.body, { status: response.status, headers });
    }
    return response;
  },
};
