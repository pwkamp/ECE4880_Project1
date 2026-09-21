export interface SmsMessage {
  to: string;
  body: string;
  subject?: string;
  html?: string;
}

export interface SmsResult {
  /** 'sent' via a real provider; 'logged' by the console sender. */
  status: 'sent' | 'logged';
  /** SMTP message id when status is 'sent'. */
  providerId?: string;
}

export interface SmsSender {
  /** Resolves on success; rejects (throws) on provider failure. */
  send(msg: SmsMessage): Promise<SmsResult>;
}
