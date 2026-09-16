import { existsSync } from 'node:fs';

/** Load a dotenv file into process.env if it exists. Returns whether it loaded. */
export function loadServerEnv(filename = 'server/.env'): boolean {
  if (!existsSync(filename)) return false;
  process.loadEnvFile(filename);
  return true;
}
