import type { SmsSender } from './types.ts';

/** A sender that only prints the message. The default in local dev. */
export function createConsoleSmsSender(): SmsSender {
  return {
    async send(msg) {
      console.log(`[sms:console] to=${msg.to} body=${JSON.stringify(msg.body)}`);
      return { status: 'logged' };
    },
  };
}
