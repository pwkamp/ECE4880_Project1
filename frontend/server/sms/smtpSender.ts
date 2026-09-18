import nodemailer from 'nodemailer';
import type { SmtpConfig } from '../config.ts';
import type { SmsSender } from './types.ts';

/** Real delivery through SMTP. Gmail works from this machine with an app password. */
export function createSmtpEmailSender(config: SmtpConfig): SmsSender {
  const transport = nodemailer.createTransport({
    host: config.host,
    port: config.port,
    secure: config.secure,
    auth: { user: config.user, pass: config.pass },
  });
  return {
    async send(msg) {
      const info = await transport.sendMail({
        from: config.fromEmail,
        to: msg.to,
        subject: 'Thermometer alert',
        text: msg.body,
      });
      return { status: 'sent', providerId: info.messageId };
    },
  };
}
