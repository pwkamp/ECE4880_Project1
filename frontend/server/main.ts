import { createApp } from './app.ts';
import { loadConfig } from './config.ts';
import { loadServerEnv } from './loadEnv.ts';
import { createMysqlSampleStore } from './samples.ts';
import { createSmsSender } from './sms/index.ts';
import { createMysqlAlertConfigStore } from './alertConfig.ts';

async function main() {
  loadServerEnv();
  const config = loadConfig(process.env);
  const sender = createSmsSender(config);

  let samples = null;
  let alertConfig = null;
  if (config.mysqlUrl) {
    try {
      samples = await createMysqlSampleStore(config.mysqlUrl);
      alertConfig = await createMysqlAlertConfigStore(config.mysqlUrl);
      console.log('[alert-service] MySQL sample reader enabled');
    } catch (err) {
      console.warn('[alert-service] MySQL sample reader unavailable:', err);
    }
  }

  const app = createApp({ config, sender, samples, alertConfig });
  app.listen(config.port, '127.0.0.1', () => {
    console.log(
      `[alert-service] http://127.0.0.1:${config.port}  (EMAIL_MODE=${config.mode})`,
    );
  });
}

void main();
