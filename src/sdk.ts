import { FeedSource, SDKConfig, Article, Newsletter } from './types';
import { RSSAgent } from './agents/RSSAgent';
import { ScraperAgent } from './agents/ScraperAgent';
import { PersonalizerAgent } from './agents/PersonalizerAgent';
import { EmailAgent } from './agents/EmailAgent';
import { generateNewsletterHtml } from './templates/emailTemplate';
import * as fs from 'fs';
import * as path from 'path';

export class ClaudeNewsSDK {
  private config: SDKConfig;
  private sources: FeedSource[] = [];

  constructor(config: SDKConfig) {
    this.config = config;
    if (config.sources) {
      this.sources = [...config.sources];
    }
  }

  /**
   * Helper to easily register an RSS feed source.
   */
  addRSSSource(name: string, url: string, id?: string): this {
    const sourceId = id || `rss-${Math.random().toString(36).substring(2, 9)}`;
    this.sources.push({
      id: sourceId,
      name,
      type: 'rss',
      url,
      enabled: true
    });
    console.log(`[ClaudeNewsSDK] Registered RSS Source: "${name}" (${url})`);
    return this;
  }

  /**
   * Helper to easily register a Website Scraping source.
   * Options allow defining optional selectors to target elements.
   */
  addWebSource(
    name: string,
    url: string,
    options?: {
      id?: string;
      selector?: string;
      titleSelector?: string;
      linkSelector?: string;
      snippetSelector?: string;
    }
  ): this {
    const sourceId = options?.id || `web-${Math.random().toString(36).substring(2, 9)}`;
    this.sources.push({
      id: sourceId,
      name,
      type: 'web',
      url,
      selector: options?.selector,
      titleSelector: options?.titleSelector,
      linkSelector: options?.linkSelector,
      snippetSelector: options?.snippetSelector,
      enabled: true
    });
    console.log(`[ClaudeNewsSDK] Registered Web Source: "${name}" (${url})`);
    return this;
  }

  /**
   * Execute the multi-agent news compilation pipeline:
   * 1. Run RSS & Web scraper child agents in parallel.
   * 2. Combine and deduplicate articles.
   * 3. Send to PersonalizerAgent (Claude) to filter/summarize.
   * 4. Compile HTML using the premium email template.
   * 5. Send via Resend.
   */
  async run(): Promise<{ newsletter: Newsletter; emailId: string }> {
    console.log('[ClaudeNewsSDK] Starting personalized news compilation pipeline...');

    const activeSources = this.sources.filter((s) => s.enabled !== false);
    if (activeSources.length === 0) {
      throw new Error('No sources registered. Please call addRSSSource() or addWebSource() first.');
    }

    // 1. Initialize child agents
    const childAgents = activeSources.map((source) => {
      if (source.type === 'rss') {
        return new RSSAgent(source);
      } else {
        return new ScraperAgent(source);
      }
    });

    // 2. Fetch data in parallel using Promise.all
    console.log(`[ClaudeNewsSDK] Harvesting feeds in parallel with ${childAgents.length} child agents...`);
    const results = await Promise.all(
      childAgents.map((agent) =>
        agent.run().catch((error) => {
          console.error(`[ClaudeNewsSDK] Child agent "${agent.name}" encountered an error:`, error);
          return [] as Article[];
        })
      )
    );

    // Flatten and deduplicate articles by link
    const allArticles = results.flat();
    const uniqueArticles = this.deduplicateArticles(allArticles);
    console.log(`[ClaudeNewsSDK] Harvest complete. Combined ${allArticles.length} items to ${uniqueArticles.length} unique articles.`);

    if (uniqueArticles.length === 0) {
      console.warn('[ClaudeNewsSDK] No articles were fetched from the registered sources.');
    }

    // 3. Personalize and compile utilizing Claude
    const personalizer = new PersonalizerAgent(
      this.config.anthropicApiKey,
      this.config.userProfile,
      this.config.model
    );
    const newsletter = await personalizer.run(uniqueArticles);

    // 4. Render HTML Newsletter using template
    const htmlContent = generateNewsletterHtml(newsletter, this.config.userProfile);

    // 5. Send via Resend
    const emailAgent = new EmailAgent({
      resendApiKey: this.config.resendApiKey,
      toEmail: this.config.userProfile.email,
      fromEmail: this.config.fromEmail
    });

    const emailId = await emailAgent.send(newsletter.title, htmlContent);

    console.log('[ClaudeNewsSDK] Pipeline completed successfully!');
    return { newsletter, emailId };
  }

  /**
   * Helper to deduplicate articles based on link.
   */
  private deduplicateArticles(articles: Article[]): Article[] {
    const seen = new Set<string>();
    return articles.filter((art) => {
      if (!art.link) return false;
      const normalized = art.link.trim().toLowerCase().replace(/\/$/, '');
      if (seen.has(normalized)) {
        return false;
      }
      seen.add(normalized);
      return true;
    });
  }

  /**
   * Helper to load sources from a JSON file.
   */
  loadSourcesFromJson(filePath: string): this {
    try {
      const absolutePath = path.resolve(filePath);
      if (!fs.existsSync(absolutePath)) {
        console.warn(`[ClaudeNewsSDK] Sources JSON file not found at ${absolutePath}`);
        return this;
      }
      const fileContent = fs.readFileSync(absolutePath, 'utf8');
      const loadedSources = JSON.parse(fileContent) as FeedSource[];
      
      for (const source of loadedSources) {
        if (!source.id) {
          source.id = `${source.type}-${Math.random().toString(36).substring(2, 9)}`;
        }
        if (source.enabled === undefined) {
          source.enabled = true;
        }
        this.sources.push(source);
      }
      console.log(`[ClaudeNewsSDK] Successfully loaded ${loadedSources.length} sources from ${filePath}`);
    } catch (error) {
      console.error(`[ClaudeNewsSDK] Error loading sources from JSON file:`, error);
    }
    return this;
  }
}
