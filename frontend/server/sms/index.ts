import type { Config } from '../config.ts';
import { createConsoleSmsSender } from './consoleSender.ts';
import { createSmtpEmailSender } from './smtpSender.ts';
import type { SmsSender } from './types.ts';

export function createSmsSender(config: Config): SmsSender {
  if (config.mode === 'console' || config.smtp === null) {
    return createConsoleSmsSender();
  }
  return createSmtpEmailSender(config.smtp);
}
