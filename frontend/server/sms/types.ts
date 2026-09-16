export interface SmsMessage {
  to: string;
  body: string;
}

export interface SmsResult {
  /** 'sent' via a real provider; 'logged' by the console sender. */
  status: 'sent' | 'logged';
  /** Provider-side id (Twilio message SID) when status is 'sent'. */
  providerId?: string;
}

export interface SmsSender {
  /** Resolves on success; rejects (throws) on provider failure. */
  send(msg: SmsMessage): Promise<SmsResult>;
}
