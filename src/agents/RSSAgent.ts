import Parser from 'rss-parser';
import { BaseAgent } from './BaseAgent';
import { Article, RSSSource } from '../types';

export class RSSAgent extends BaseAgent {
  private url: string;
  private parser: Parser;

  constructor(source: RSSSource) {
    super(source.id, source.name);
    this.url = source.url;
    this.parser = new Parser();
  }

  async run(): Promise<Article[]> {
    console.log(`[RSSAgent:${this.name}] Fetching RSS feed from: ${this.url}`);
    try {
      const feed = await this.parser.parseURL(this.url);
      
      const articles: Article[] = feed.items.map((item) => {
        return {
          sourceId: this.id,
          sourceName: this.name,
          title: item.title || 'Untitled Article',
          link: item.link || '',
          pubDate: item.pubDate || item.isoDate,
          snippet: item.contentSnippet || item.summary || item.content || '',
          content: item.content || ''
        };
      });

      console.log(`[RSSAgent:${this.name}] Successfully fetched ${articles.length} articles`);
      return articles.filter(art => art.link !== ''); // Only keep articles with links
    } catch (error) {
      console.error(`[RSSAgent:${this.name}] Error fetching or parsing RSS feed:`, error);
      return [];
    }
  }
}
