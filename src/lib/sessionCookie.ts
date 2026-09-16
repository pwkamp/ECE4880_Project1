/**
 * SCRUM-628 / SWE-SEC-LLR-753 - Session Cookie Protection.
 *
 * STATUS: this repository is a static Vite + React frontend. There is no
 * backend, no `express-session`, no JWT-in-cookie flow - nothing issues an
 * authentication cookie today, so there is no live `Set-Cookie` configuration
 * to harden. This module captures the required security decision as reviewed
 * code so that whenever a session layer is introduced it consumes these options
 * from one place instead of hand-rolling cookie flags.
 *
 * The shape matches the `cookie` option bag used by express-session / Fastify /
 * `res.cookie`, so it can be spread straight in:
 *
 *   app.use(session({ secret, cookie: sessionCookieOptions({ https: isProd }) }));
 */

export interface SessionCookieOptions {
  /**
   * SCRUM-628 AC: HttpOnly is ALWAYS true. Client-side JavaScript must never be
   * able to read the session cookie, which neutralises session-token theft via
   * XSS.
   */
  httpOnly: true;
  /**
   * SCRUM-628 AC: Secure whenever the deployment is served over HTTPS. Defaults
   * from the build mode for convenience; a real backend should pass `https`
   * explicitly from its own environment / TLS-termination config.
   */
  secure: boolean;
  /**
   * SCRUM-628 AC: an explicit SameSite policy. Chosen value: "lax".
   *
   * Why "lax":
   *  - It withholds the cookie from cross-site subrequests (cross-origin form
   *    POSTs, fetch, iframes), closing the common CSRF vector, while still
   *    sending it on top-level GET navigations - so an inbound link (e.g. an
   *    alert email pointing at a dashboard view) still lands authenticated.
   *  - "strict" would drop the cookie on those inbound top-level links, logging
   *    the operator out whenever they arrive from another origin. That is poor
   *    UX for a monitoring console and buys no extra protection here.
   *  - "none" is only for deliberate cross-site usage (third-party embedding),
   *    which this app does not do. It also mandates Secure and widens the CSRF
   *    surface for no benefit.
   */
  sameSite: 'lax';
  /** Cookie scoped to the whole app. */
  path: '/';
}

export interface SessionCookieEnv {
  /** True when the deployment serves over HTTPS (production). */
  https?: boolean;
}

/** `vite build` sets this to true; dev and test builds leave it false. */
function httpsFromBuildMode(): boolean {
  return import.meta.env.PROD;
}

export function sessionCookieOptions(
  env: SessionCookieEnv = {},
): SessionCookieOptions {
  return {
    httpOnly: true,
    secure: env.https ?? httpsFromBuildMode(),
    sameSite: 'lax',
    path: '/',
  };
}
