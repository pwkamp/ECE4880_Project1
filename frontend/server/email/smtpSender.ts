import nodemailer from 'nodemailer';
import type { SmtpConfig } from '../config.ts';
import type { EmailSender } from './types.ts';

/** Real delivery through SMTP. Gmail works from this machine with an app password. */
export function createSmtpEmailSender(config: SmtpConfig): EmailSender {
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
        subject: msg.subject ?? 'Thermometer alert',
        text: msg.body,
        html: msg.html,
      });
      return { status: 'sent', providerId: info.messageId };
    },
  };
}
