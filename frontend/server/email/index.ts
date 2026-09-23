import type { Config } from '../config.ts';
import { createConsoleEmailSender } from './consoleSender.ts';
import { createSmtpEmailSender } from './smtpSender.ts';
import type { EmailSender } from './types.ts';

export function createEmailSender(config: Config): EmailSender {
  if (config.mode === 'console' || config.smtp === null) {
    return createConsoleEmailSender();
  }
  return createSmtpEmailSender(config.smtp);
}
