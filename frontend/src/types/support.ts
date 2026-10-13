/**
 * POST /support/contact request body
 * (backend/app/schemas/support.py - SupportContactRequest). Public - no
 * authentication required, submitted from the Help Center's contact form.
 *
 * `website` is a honeypot: never shown to or filled in by a real visitor
 * (see HelpCenterPage.tsx's hidden field), left undefined/empty on every
 * genuine submission. A bot that blindly fills every input in a scraped
 * form will fill it too - the backend silently drops that submission
 * instead of emailing it, without saying so in the response.
 */
export interface SupportContactRequest {
  name: string;
  email: string;
  subject: string;
  message: string;
  website?: string;
}

/** POST /support/contact response body. */
export interface SupportContactResponse {
  message: string;
}
