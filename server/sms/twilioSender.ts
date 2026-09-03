import twilio from 'twilio';
import type { TwilioConfig } from '../config.ts';
import type { SmsSender } from './types.ts';

/** Real delivery through Twilio. Used for both `test` and `live` modes — the
 *  only difference is which credentials config.ts supplied. */
export function createTwilioSmsSender(config: TwilioConfig): SmsSender {
  const client = twilio(config.accountSid, config.authToken);
  return {
    async send(msg) {
      const message = await client.messages.create({
        to: msg.to,
        from: config.fromNumber,
        body: msg.body,
      });
      return { status: 'sent', providerId: message.sid };
    },
  };
}
