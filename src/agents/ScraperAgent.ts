import * as cheerio from 'cheerio';
import { BaseAgent } from './BaseAgent';
import { Article, WebSource } from '../types';

export class ScraperAgent extends BaseAgent {
  private url: string;
  private selector?: string;
  private titleSelector?: string;
  private linkSelector?: string;
  private snippetSelector?: string;

  constructor(source: WebSource) {
    super(source.id, source.name);
    this.url = source.url;
    this.selector = source.selector;
    this.titleSelector = source.titleSelector;
    this.linkSelector = source.linkSelector;
    this.snippetSelector = source.snippetSelector;
  }

  async run(): Promise<Article[]> {
    console.log(`[ScraperAgent:${this.name}] Scraping website: ${this.url}`);
    try {
      const response = await fetch(this.url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP status ${response.status}`);
      }

      const html = await response.text();
      const $ = cheerio.load(html);
      const articles: Article[] = [];

      // Resolve relative URL to absolute URL
      const makeAbsolute = (link: string) => {
        if (!link) return '';
        try {
          return new URL(link, this.url).href;
        } catch {
          return link;
        }
      };

      if (this.selector) {
        // Targeted CSS Selector Scraping
        $(this.selector).each((_, element) => {
          const el = $(element);
          
          let title = '';
          if (this.titleSelector) {
            title = el.find(this.titleSelector).first().text().trim();
          } else {
            // Fallback: try finding first h1, h2, h3, or a tag text
            title = el.find('h1, h2, h3, h4, a').first().text().trim() || el.text().trim().substring(0, 100);
          }

          let link = '';
          if (this.linkSelector) {
            link = el.find(this.linkSelector).first().attr('href') || '';
          } else {
            // Fallback: first href in the element
            link = el.find('a').first().attr('href') || el.attr('href') || '';
          }

          let snippet = '';
          if (this.snippetSelector) {
            snippet = el.find(this.snippetSelector).first().text().trim();
          } else {
            // Fallback: try finding a paragraph or span
            snippet = el.find('p, span, .description, .summary, .excerpt').first().text().trim();
          }

          if (title && link) {
            articles.push({
              sourceId: this.id,
              sourceName: this.name,
              title,
              link: makeAbsolute(link),
              snippet: snippet.substring(0, 300) // keep snippets reasonable
            });
          }
        });
      } else {
        // Heuristic fallback: Search for headings with links (H1, H2, H3)
        $('h1, h2, h3, h4').each((_, element) => {
          const el = $(element);
          const linkEl = el.find('a').first();
          if (linkEl.length > 0) {
            const title = el.text().trim();
            const link = linkEl.attr('href') || '';
            // Try to find adjacent/nearby paragraphs
            const parent = el.parent();
            const snippet = parent.find('p').first().text().trim() || '';

            if (title && link && title.length > 5) {
              articles.push({
                sourceId: this.id,
                sourceName: this.name,
                title,
                link: makeAbsolute(link),
                snippet: snippet.substring(0, 300)
              });
            }
          }
        });

        // Alternate heuristic fallback: look for list items containing links with substantial text
        if (articles.length === 0) {
          $('li, div.post, div.item').each((_, element) => {
            const el = $(element);
            const linkEl = el.find('a').first();
            if (linkEl.length > 0) {
              const link = linkEl.attr('href') || '';
              const title = linkEl.text().trim();
              const snippet = el.text().replace(title, '').trim();

              if (title && link && title.length > 10 && link.length > 5) {
                articles.push({
                  sourceId: this.id,
                  sourceName: this.name,
                  title,
                  link: makeAbsolute(link),
                  snippet: snippet.substring(0, 300)
                });
              }
            }
          });
        }
      }

      console.log(`[ScraperAgent:${this.name}] Successfully scraped ${articles.length} raw items`);
      
      // De-duplicate articles by link
      const uniqueArticles: Article[] = [];
      const seenLinks = new Set<string>();
      for (const art of articles) {
        if (art.link && !seenLinks.has(art.link)) {
          seenLinks.add(art.link);
          uniqueArticles.push(art);
        }
      }

      return uniqueArticles.slice(0, 15); // limit to 15 articles per web scraping run
    } catch (error) {
      console.error(`[ScraperAgent:${this.name}] Error scraping URL:`, error);
      return [];
    }
  }
}
