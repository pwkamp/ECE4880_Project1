import { expect, it, vi } from 'vitest';

vi.mock('nodemailer', () => ({
  default: {
    createTransport: vi.fn(() => ({
      sendMail: vi.fn(async () => ({ messageId: '<id@gmail.com>' })),
    })),
  },
}));

import nodemailer from 'nodemailer';
import { createSmtpEmailSender } from './smtpSender.ts';

it('sends mail through the SMTP transport', async () => {
  const sendMail = vi.fn(async () => ({ messageId: '<id@gmail.com>' }));
  vi.mocked(nodemailer.createTransport).mockReturnValue({ sendMail } as never);

  const sender = createSmtpEmailSender({
    host: 'smtp.gmail.com',
    port: 465,
    secure: true,
    user: 'alerts@gmail.com',
    pass: 'app-password',
    fromEmail: 'alerts@gmail.com',
  });

  await expect(
    sender.send({
      to: 'you@example.com',
      body: 'hot',
      subject: 'HIGH temperature alert - Sensor 1 at 34.2°C',
      html: '<p>hot</p>',
    }),
  ).resolves.toEqual({
    status: 'sent',
    providerId: '<id@gmail.com>',
  });
  expect(sendMail).toHaveBeenCalledWith(
    expect.objectContaining({
      from: 'alerts@gmail.com',
      to: 'you@example.com',
      subject: 'HIGH temperature alert - Sensor 1 at 34.2°C',
      text: 'hot',
      html: '<p>hot</p>',
    }),
  );
});
