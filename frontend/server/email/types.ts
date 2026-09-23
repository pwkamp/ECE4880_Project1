export interface EmailMessage {
  to: string;
  body: string;
  subject?: string;
  html?: string;
}

export interface EmailResult {
  /** 'sent' via a real provider; 'logged' by the console sender. */
  status: 'sent' | 'logged';
  /** SMTP message id when status is 'sent'. */
  providerId?: string;
}

export interface EmailSender {
  /** Resolves on success; rejects (throws) on provider failure. */
  send(msg: EmailMessage): Promise<EmailResult>;
}
