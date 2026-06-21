import { Resend } from 'resend';
import { Newsletter } from '../types';

export interface EmailAgentConfig {
  resendApiKey: string;
  fromEmail?: string;
  toEmail: string;
}

export class EmailAgent {
  private resend: Resend;
  private fromEmail: string;
  private toEmail: string;

  constructor(config: EmailAgentConfig) {
    this.resend = new Resend(config.resendApiKey);
    // Resend free tier/onboarding emails must come from 'onboarding@resend.dev' unless you verify a domain.
    this.fromEmail = config.fromEmail || 'News Briefing <onboarding@resend.dev>';
    this.toEmail = config.toEmail;
  }

  /**
   * Sends the compiled HTML newsletter via Resend.
   * Returns the message ID if successful.
   */
  async send(subject: string, htmlContent: string): Promise<string> {
    console.log(`[EmailAgent] Sending email to ${this.toEmail} using Resend...`);
    try {
      const response = await this.resend.emails.send({
        from: this.fromEmail,
        to: [this.toEmail],
        subject: subject,
        html: htmlContent,
      });

      if (response.error) {
        throw new Error(response.error.message);
      }

      const emailId = response.data?.id || 'unknown';
      console.log(`[EmailAgent] Newsletter email successfully sent! Email ID: ${emailId}`);
      return emailId;
    } catch (error) {
      console.error(`[EmailAgent] Failed to send email via Resend:`, error);
      throw error;
    }
  }
}
