import type { SmsSender } from './types.ts';

/** A sender that only prints the message. The default in local dev. */
export function createConsoleSmsSender(): SmsSender {
  return {
    async send(msg) {
      console.log(`Email sent to ${msg.to}: ${JSON.stringify(msg.subject ?? msg.body)}`);
      return { status: 'logged' };
    },
  };
}
