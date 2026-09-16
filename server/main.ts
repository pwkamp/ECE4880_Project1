import { createApp } from './app.ts';
import { loadConfig } from './config.ts';
import { loadServerEnv } from './loadEnv.ts';
import { createMysqlSampleStore } from './samples.ts';
import { createSmsSender } from './sms/index.ts';

async function main() {
  loadServerEnv();
  const config = loadConfig(process.env);
  const sender = createSmsSender(config);

  let samples = null;
  if (config.mysqlUrl) {
    try {
      samples = await createMysqlSampleStore(config.mysqlUrl);
      console.log('[alert-service] MySQL sample reader enabled');
    } catch (err) {
      console.warn('[alert-service] MySQL sample reader unavailable:', err);
    }
  }

  const app = createApp({ config, sender, samples });
  app.listen(config.port, '127.0.0.1', () => {
    console.log(
      `[alert-service] http://127.0.0.1:${config.port}  (SMS_MODE=${config.mode})`,
    );
  });
}

void main();
