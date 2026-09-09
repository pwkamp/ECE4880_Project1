import { expect, test } from 'vitest';
import { sessionCookieOptions } from './sessionCookie';

test('SCRUM-628: HttpOnly is always true', () => {
  expect(sessionCookieOptions({ https: true }).httpOnly).toBe(true);
  expect(sessionCookieOptions({ https: false }).httpOnly).toBe(true);
});

test('SCRUM-628: Secure follows the HTTPS deployment flag', () => {
  expect(sessionCookieOptions({ https: true }).secure).toBe(true);
  expect(sessionCookieOptions({ https: false }).secure).toBe(false);
});

test('SCRUM-628: SameSite is an explicit "lax"', () => {
  expect(sessionCookieOptions({ https: true }).sameSite).toBe('lax');
  expect(sessionCookieOptions().sameSite).toBe('lax');
});
