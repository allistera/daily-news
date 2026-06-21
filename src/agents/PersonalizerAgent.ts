import Anthropic from '@anthropic-ai/sdk';
import { Article, Newsletter, UserProfile } from '../types';

export class PersonalizerAgent {
  private anthropic: Anthropic;
  private userProfile: UserProfile;
  private model: string;

  constructor(apiKey: string, userProfile: UserProfile, model = 'claude-3-5-sonnet-latest') {
    this.anthropic = new Anthropic({ apiKey });
    this.userProfile = userProfile;
    this.model = model;
  }

  /**
   * Evaluates collected articles against user preferences, filters out low-relevance items,
   * compiles the top selections into categorized groups, and returns a structured Newsletter object.
   */
  async run(articles: Article[]): Promise<Newsletter> {
    console.log(`[PersonalizerAgent] Filtering and personalizing ${articles.length} articles for ${this.userProfile.name}...`);
    
    if (articles.length === 0) {
      return this.createEmptyNewsletter();
    }

    const todayStr = new Date().toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });

    const systemPrompt = `You are a world-class curator and personal news assistant. Your job is to read a list of articles and compile a highly curated, personalized email newsletter.

User Profile:
- Name: ${this.userProfile.name}
- Email: ${this.userProfile.email}
- Key Interests: ${this.userProfile.interests.join(', ')}
${this.userProfile.tone ? `- Preferred Tone: ${this.userProfile.tone}` : ''}
${this.userProfile.additionalPreferences ? `- Additional Rules/Preferences: ${this.userProfile.additionalPreferences}` : ''}

Today's Date: ${todayStr}

Tasks:
1. Score each article on a scale of 1 to 10 based on how relevant it is to the user's interests. (10 is extremely relevant/must-read, 1 is irrelevant).
2. Filter out articles with a relevance score below 7.0 (or keep the top 6-10 articles if there are many articles). Do not list more than 10 articles.
3. Group the selected articles into 2 to 4 logical sections/categories (e.g. "Artificial Intelligence", "General Tech", "Finance & Space").
4. For each selected article:
   - Provide a concise summary (2-3 sentences) of the article.
   - Provide a brief relevance explanation (1-2 sentences) showing why this fits the user's specific interests.
5. Create a catchy, personalized subject/title for the newsletter.
6. Write a friendly, introductory message (intro) explaining today's edition, written in the user's preferred tone.
7. Write a short, engaging closing remark (outro).

You MUST output ONLY a valid JSON object matching the following structure:
{
  "title": "A catchy, custom newsletter title, e.g. 'Daily Digest: AI Breakthroughs & Space Exploration'",
  "date": "${todayStr}",
  "intro": "A friendly personalized greeting and summary of the newsletter themes...",
  "sections": [
    {
      "category": "Section Category Title (e.g. AI & Machine Learning)",
      "description": "Brief description of the theme of this section (1 sentence)",
      "articles": [
        {
          "title": "Exact or slightly cleaned article title",
          "link": "Article URL",
          "sourceName": "Source name",
          "relevanceScore": 9.2,
          "relevanceExplanation": "Why this fits the user's specific interest in...",
          "summary": "A 2-3 sentence engaging summary of what the article covers."
        }
      ]
    }
  ],
  "outro": "A brief sign-off..."
}

CRITICAL: Return ONLY valid JSON wrapped in a \`\`\`json markdown block. Do not write any conversational text before or after the markdown block.`;

    const userMessage = `Here are the articles harvested by my child agents:

${JSON.stringify(articles.map((a, idx) => ({
      index: idx,
      title: a.title,
      link: a.link,
      sourceName: a.sourceName,
      snippet: a.snippet
    })), null, 2)}

Please filter, score, organize, and compile these into the JSON newsletter.`;

    try {
      const response = await this.anthropic.messages.create({
        model: this.model,
        max_tokens: 4000,
        system: systemPrompt,
        messages: [
          { role: 'user', content: userMessage }
        ]
      });

      const rawText = response.content[0].type === 'text' ? response.content[0].text : '';
      const newsletter = this.parseNewsletterJson(rawText);
      console.log(`[PersonalizerAgent] Successfully personalized and compiled newsletter with ${
        newsletter.sections.reduce((acc, sec) => acc + sec.articles.length, 0)
      } articles.`);
      
      return newsletter;
    } catch (error) {
      console.error('[PersonalizerAgent] Error compiling newsletter with Claude:', error);
      throw error;
    }
  }

  private parseNewsletterJson(text: string): Newsletter {
    try {
      // Find code blocks if present
      const jsonMatch = text.match(/```json\s*([\s\S]*?)\s*```/) || text.match(/```\s*([\s\S]*?)\s*```/);
      const jsonString = jsonMatch ? jsonMatch[1] : text;
      
      const parsed = JSON.parse(jsonString.trim());
      
      // Basic validation of fields
      if (!parsed.title || !parsed.intro || !Array.isArray(parsed.sections)) {
        throw new Error('Invalid JSON structure returned by Claude');
      }

      return parsed as Newsletter;
    } catch (error) {
      console.error('[PersonalizerAgent] Raw response failed to parse:', text);
      throw new Error(`Failed to parse Claude response into valid newsletter JSON: ${(error as Error).message}`);
    }
  }

  private createEmptyNewsletter(): Newsletter {
    const todayStr = new Date().toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
    return {
      title: `Personal Briefing: No News Found`,
      date: todayStr,
      intro: `Hello ${this.userProfile.name}. We checked your sources today but couldn't find any articles to curate.`,
      sections: [],
      outro: `We will check again tomorrow! Have a great day.`
    };
  }
}
