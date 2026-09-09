import { createApp } from './app.ts';
import { loadConfig } from './config.ts';
import { loadServerEnv } from './loadEnv.ts';
import { createSmsSender } from './sms/index.ts';

loadServerEnv();
const config = loadConfig(process.env);
const sender = createSmsSender(config);
const app = createApp({ config, sender });

app.listen(config.port, '127.0.0.1', () => {
  console.log(`[alert-service] http://127.0.0.1:${config.port}  (SMS_MODE=${config.mode})`);
});
