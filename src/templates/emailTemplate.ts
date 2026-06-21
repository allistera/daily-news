import { Newsletter, UserProfile } from '../types';

/**
 * Generates a beautifully styled, premium HTML email newsletter
 * based on the compiled and personalized newsletter data.
 */
export function generateNewsletterHtml(newsletter: Newsletter, profile: UserProfile): string {
  const sectionsHtml = newsletter.sections
    .map((section) => {
      if (section.articles.length === 0) return '';
      
      const articlesHtml = section.articles
        .map((article) => {
          // Color badge based on relevance score
          let scoreBg = '#0f172a';
          let scoreText = '#38bdf8';
          if (article.relevanceScore >= 9) {
            scoreBg = '#134e4a';
            scoreText = '#2dd4bf';
          } else if (article.relevanceScore >= 7) {
            scoreBg = '#1e3a8a';
            scoreText = '#60a5fa';
          }

          return `
            <div class="article-card" style="background-color: #161f38; border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid #233154; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 12px;">
                      <tr>
                        <td style="background-color: #233154; color: #cbd5e1; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.05em; font-family: sans-serif; display: inline-block;">
                          ${escapeHtml(article.sourceName)}
                        </td>
                        <td style="width: 8px;"></td>
                        <td style="background-color: ${scoreBg}; color: ${scoreText}; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.05em; font-family: sans-serif; display: inline-block;">
                          ${article.relevanceScore.toFixed(1)}/10 Match
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td>
                    <h3 style="margin: 0 0 10px 0; font-size: 18px; font-weight: 700; line-height: 1.4; color: #ffffff; font-family: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                      <a href="${article.link}" target="_blank" style="color: #ffffff; text-decoration: none; border-bottom: 1px dashed #475569;">
                        ${escapeHtml(article.title)}
                      </a>
                    </h3>
                  </td>
                </tr>
                <tr>
                  <td>
                    <p style="margin: 0 0 14px 0; font-size: 14px; line-height: 1.6; color: #94a3b8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                      ${escapeHtml(article.summary)}
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="background-color: rgba(56, 189, 248, 0.04); border-left: 3px solid #38bdf8; padding: 8px 12px; margin-bottom: 15px; border-radius: 0 6px 6px 0;">
                    <p style="margin: 0; font-size: 12.5px; font-style: italic; color: #38bdf8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                      <strong style="font-weight: 600; font-style: normal; text-transform: uppercase; font-size: 10px; letter-spacing: 0.05em; display: inline-block; margin-right: 4px;">Why this matters:</strong>
                      ${escapeHtml(article.relevanceExplanation)}
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="padding-top: 10px;">
                    <a href="${article.link}" target="_blank" style="background-color: #38bdf8; color: #0a0f1d; font-size: 13px; font-weight: 600; text-decoration: none; padding: 8px 18px; border-radius: 6px; display: inline-block; font-family: sans-serif; transition: background-color 0.2s;">
                      Read Article &rarr;
                    </a>
                  </td>
                </tr>
              </table>
            </div>
          `;
        })
        .join('');

      return `
        <div class="section-container" style="margin-bottom: 40px;">
          <h2 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: #38bdf8; border-bottom: 2px solid #233154; padding-bottom: 8px; font-family: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            ${escapeHtml(section.category)}
            ${section.description ? `<span style="font-size: 12px; text-transform: none; font-weight: 400; color: #64748b; margin-left: 8px; letter-spacing: 0;">${escapeHtml(section.description)}</span>` : ''}
          </h2>
          ${articlesHtml}
        </div>
      `;
    })
    .join('');

  return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(newsletter.title)}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    body {
      background-color: #0a0f1d;
      margin: 0;
      padding: 0;
      -webkit-text-size-adjust: 100%;
      -ms-text-size-adjust: 100%;
    }
    @media only screen and (max-width: 600px) {
      .container {
        width: 100% !important;
        padding: 10px !important;
      }
      .header-title {
        font-size: 28px !important;
      }
    }
  </style>
</head>
<body style="background-color: #0a0f1d; font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #e2e8f0; margin: 0; padding: 20px 0;">
  <center>
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #0a0f1d; max-width: 650px; margin: 0 auto; text-align: left;" class="container">
      <!-- HEADER -->
      <tr>
        <td style="padding: 30px 20px 20px 20px; border-bottom: 1px solid #1e293b; background: linear-gradient(135deg, #0f172a 0%, #0a0f1d 100%); border-radius: 16px 16px 0 0;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td>
                <span style="color: #38bdf8; font-size: 11px; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; font-family: sans-serif; display: block; margin-bottom: 6px;">
                  CLAUDE POWERED INTELLIGENCE BRIEFING
                </span>
                <h1 class="header-title" style="margin: 0 0 10px 0; font-size: 32px; font-weight: 800; color: #ffffff; letter-spacing: -0.02em; font-family: 'Outfit', sans-serif;">
                  ${escapeHtml(newsletter.title)}
                </h1>
                <p style="margin: 0; font-size: 14px; color: #94a3b8; font-family: sans-serif;">
                  Prepared for <strong style="color: #f1f5f9;">${escapeHtml(profile.name)}</strong> on <strong>${escapeHtml(newsletter.date)}</strong>
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- INTRO -->
      <tr>
        <td style="padding: 25px 20px; background-color: #0f172a; border-left: 1px solid #1e293b; border-right: 1px solid #1e293b;">
          <p style="margin: 0; font-size: 15px; line-height: 1.6; color: #cbd5e1;">
            ${escapeHtml(newsletter.intro).replace(/\n/g, '<br>')}
          </p>
        </td>
      </tr>

      <!-- NEWS ARTICLES SECTIONS -->
      <tr>
        <td style="padding: 30px 20px; background-color: #0a0f1d; border-left: 1px solid #1e293b; border-right: 1px solid #1e293b;">
          ${sectionsHtml}
        </td>
      </tr>

      <!-- OUTRO -->
      <tr>
        <td style="padding: 25px 20px; background-color: #0f172a; border-top: 1px solid #1e293b; border-left: 1px solid #1e293b; border-right: 1px solid #1e293b; border-radius: 0 0 16px 16px;">
          <p style="margin: 0 0 15px 0; font-size: 14.5px; line-height: 1.6; color: #cbd5e1; font-style: italic;">
            ${escapeHtml(newsletter.outro).replace(/\n/g, '<br>')}
          </p>
          <div style="border-top: 1px solid #1e293b; padding-top: 15px; margin-top: 15px;">
            <p style="margin: 0; font-size: 11px; color: #64748b; line-height: 1.5; font-family: sans-serif;">
              <strong>Personalization Profile:</strong> Interested in <em>${escapeHtml(profile.interests.join(', '))}</em>. 
              ${profile.additionalPreferences ? `Custom rules: ${escapeHtml(profile.additionalPreferences)}` : ''}
            </p>
          </div>
        </td>
      </tr>

      <!-- FOOTER -->
      <tr>
        <td style="padding: 20px; text-align: center;">
          <p style="margin: 0; font-size: 11px; color: #475569; font-family: sans-serif;">
            Generated automatically by Claude News SDK.
            <br>
            Powered by Anthropic Claude 3.5 &amp; Resend.
          </p>
        </td>
      </tr>
    </table>
  </center>
</body>
</html>
  `;
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
