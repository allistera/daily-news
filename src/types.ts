export interface UserProfile {
  name: string;
  email: string;
  interests: string[];
  tone?: string; // e.g. "informative", "humorous", "brief & punchy"
  additionalPreferences?: string;
}

export type FeedType = 'rss' | 'web';

export interface BaseSource {
  id: string;
  name: string;
  type: FeedType;
  enabled?: boolean;
}

export interface RSSSource extends BaseSource {
  type: 'rss';
  url: string;
}

export interface WebSource extends BaseSource {
  type: 'web';
  url: string;
  /**
   * Optional CSS selector to extract article blocks from the page.
   * If omitted, a general crawler will extract paragraph content or list items.
   */
  selector?: string;
  /**
   * Optional CSS selector to parse the title within each article block.
   */
  titleSelector?: string;
  /**
   * Optional CSS selector to parse the link within each article block.
   */
  linkSelector?: string;
  /**
   * Optional CSS selector to parse the snippet/description within each article block.
   */
  snippetSelector?: string;
}

export type FeedSource = RSSSource | WebSource;

export interface Article {
  sourceId: string;
  sourceName: string;
  title: string;
  link: string;
  pubDate?: string;
  snippet?: string;
  content?: string;
}

export interface PersonalizedArticle {
  title: string;
  link: string;
  sourceName: string;
  relevanceScore: number; // 1-10
  relevanceExplanation: string;
  summary: string;
}

export interface NewsletterSection {
  category: string;
  description?: string;
  articles: PersonalizedArticle[];
}

export interface Newsletter {
  title: string;
  date: string;
  intro: string;
  sections: NewsletterSection[];
  outro: string;
}

export interface SDKConfig {
  anthropicApiKey: string;
  resendApiKey: string;
  userProfile: UserProfile;
  fromEmail?: string;
  model?: string;
  sources?: FeedSource[];
}

