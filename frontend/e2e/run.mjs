import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createServer } from 'vite';

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
process.env.VITE_DATA_SOURCE = 'ble';

const server = await createServer({
  root: frontendRoot,
  logLevel: 'warn',
  server: { host: '127.0.0.1', port: 4173, strictPort: true },
});

let exitCode = 1;
try {
  await server.listen();
  const cli = path.join(frontendRoot, 'node_modules', '@playwright', 'test', 'cli.js');
  const child = spawn(
    process.execPath,
    [cli, 'test', '--config', 'e2e/playwright.config.ts', ...process.argv.slice(2)],
    { cwd: frontendRoot, env: process.env, stdio: 'inherit' },
  );
  exitCode = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('exit', (code, signal) => resolve(code ?? (signal ? 1 : 0)));
  });
} finally {
  await server.close();
}

process.exitCode = exitCode;
