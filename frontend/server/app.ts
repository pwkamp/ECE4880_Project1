import express from 'express';
import type { Config } from './config.ts';
import { handleNotify } from './notify.ts';
import type { SampleStore } from './samples.ts';
import { PersistedAlertConfigSchema, type AlertConfigStore } from './alertConfig.ts';
import type { EmailSender } from './email/types.ts';

/** Cap on remembered event ids (oldest evicted first). */
const SEEN_LIMIT = 5000;

export function createApp(deps: {
  config: Config;
  sender: EmailSender;
  samples?: SampleStore | null;
  alertConfig?: AlertConfigStore | null;
}) {
  const app = express();
  app.use(express.json({ limit: '16kb' }));

  const seen = new Set<string>();

  if (deps.config.apiToken) {
    const expected = `Bearer ${deps.config.apiToken}`;
    app.use('/api/notify', (req, res, next) => {
      if (req.get('authorization') === expected) {
        next();
        return;
      }
      res.status(401).json({ status: 'failed', error: 'unauthorized' });
    });
  }

  app.post('/api/notify', async (req, res) => {
    const outcome = await handleNotify(req.body, { sender: deps.sender, seen });
    while (seen.size > SEEN_LIMIT) {
      const oldest = seen.values().next().value;
      if (oldest === undefined) break;
      seen.delete(oldest);
    }
    res.status(outcome.code).json(outcome.payload);
  });

  app.get('/api/health', (_req, res) => {
    res.json({ status: 'ok', mode: deps.config.mode, verification_contract: 2 });
  });

  app.get('/api/samples/latest', async (_req, res) => {
    if (!deps.samples) {
      res.json({ configured: false, row: null });
      return;
    }
    try {
      const row = await deps.samples.latest();
      res.json({ configured: true, row });
    } catch (err) {
      res.status(503).json({
        configured: true,
        error: err instanceof Error ? err.message : 'sample query failed',
      });
    }
  });

  app.get('/api/samples', async (req, res) => {
    if (!deps.samples) {
      res.json({ configured: false, rows: [] });
      return;
    }
    const seconds = Number(req.query.seconds ?? 300);
    try {
      const rows = await deps.samples.history(seconds);
      res.json({ configured: true, rows });
    } catch (err) {
      res.status(503).json({
        configured: true,
        error: err instanceof Error ? err.message : 'sample query failed',
      });
    }
  });

  app.get('/api/alert-config', async (_req, res) => {
    if (!deps.alertConfig) {
      res.status(503).json({ configured: false, error: 'alert configuration persistence is unavailable' });
      return;
    }
    try {
      res.json({ configured: true, config: await deps.alertConfig.load() });
    } catch (err) {
      res.status(503).json({ configured: true, error: err instanceof Error ? err.message : 'alert configuration query failed' });
    }
  });

  app.put('/api/alert-config', async (req, res) => {
    if (!deps.alertConfig) {
      res.status(503).json({ configured: false, error: 'alert configuration persistence is unavailable' });
      return;
    }
    const parsed = PersistedAlertConfigSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ configured: true, error: 'invalid alert configuration', detail: parsed.error.issues });
      return;
    }
    try {
      await deps.alertConfig.save(parsed.data);
      res.json({ configured: true, config: parsed.data });
    } catch (err) {
      res.status(503).json({ configured: true, error: err instanceof Error ? err.message : 'alert configuration save failed' });
    }
  });

  return app;
}
