import type { Config } from '../config.ts';
import { createConsoleSmsSender } from './consoleSender.ts';
import { createTwilioSmsSender } from './twilioSender.ts';
import type { SmsSender } from './types.ts';

export function createSmsSender(config: Config): SmsSender {
  if (config.mode === 'console' || config.twilio === null) {
    return createConsoleSmsSender();
  }
  return createTwilioSmsSender(config.twilio);
}
