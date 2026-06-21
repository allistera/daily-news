# Claude News SDK 📰🤖

A TypeScript SDK powered by Anthropic's Claude that leverages a multi-agent system to fetch, personalize, compile, and email a beautiful daily news digest.

## Architecture

The SDK orchestrates a modular pipeline using dedicated child agents:

1. **`RSSAgent` (Child Agent)**: Fetches and parses RSS feeds, converting feed items into a standardized article representation.
2. **`ScraperAgent` (Child Agent)**: Fetches raw HTML from arbitrary web pages. Supports custom CSS selectors or falls back to a smart heuristic parser that extracts article titles, links, and snippets without any upfront configuration.
3. **`PersonalizerAgent` (Claude 3.5)**: Evaluates all harvested articles against a user profile. It scores each article (1-10) for relevance, filters low-scoring articles, summarizes selections, explains why they are relevant, and structures the newsletter.
4. **`EmailAgent` (Resend)**: Sends the newsletter using a premium dark-themed HTML layout.

---

## Getting Started

### Prerequisites

- Node.js (v18+)
- Anthropic API Key (Claude)
- Resend API Key

### Installation

1. Clone or copy this repository to your project directory.
2. Install the dependencies:
   ```bash
   npm install
   ```

### Configuration

Create a `.env` file in the root directory (using `.env.example` as a template):

```env
# Anthropic API Key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Resend API Key
RESEND_API_KEY=your-resend-api-key

# Recipient Profile Details
USER_NAME=Alex
USER_EMAIL=alex@example.com
USER_INTERESTS=AI advancements,TypeScript,Space Exploration
USER_TONE=informative, modern, with a touch of wit
USER_PREFERENCES=Exclude generic marketing fluff. Focus on deep technical write-ups.
```

---

## Usage

Using the SDK is simple. Import `ClaudeNewsSDK` and register your feeds using the fluent API.

```typescript
import { ClaudeNewsSDK } from './src';

const sdk = new ClaudeNewsSDK({
  anthropicApiKey: process.env.ANTHROPIC_API_KEY!,
  resendApiKey: process.env.RESEND_API_KEY!,
  userProfile: {
    name: 'Alex',
    email: 'alex@example.com',
    interests: ['Artificial Intelligence', 'TypeScript', 'Web Development'],
    tone: 'witty and precise'
  }
});

// 1. Add standard RSS feeds
sdk.addRSSSource('Hacker News RSS', 'https://news.ycombinator.com/rss');
sdk.addRSSSource('TechCrunch AI', 'https://techcrunch.com/category/artificial-intelligence/feed/');

// 2. Add websites with custom selectors (targeted scraping)
sdk.addWebSource('TechCrunch Frontpage', 'https://techcrunch.com/', {
  selector: 'article.post-block',
  titleSelector: 'h2.post-block__title a',
  linkSelector: 'h2.post-block__title a',
  snippetSelector: 'div.post-block__content'
});

// 3. Add websites with heuristic-based scraping (no selectors required!)
sdk.addWebSource('SpaceNews', 'https://spacenews.com/segment/news/');

// 4. Run the pipeline
const result = await sdk.run();
console.log(`Newsletter "${result.newsletter.title}" sent successfully! Email ID: ${result.emailId}`);
```

### Running the Example

Run the included example script:

```bash
# If you have populated the .env file
npm run example
```

---

## GitHub Actions Automated Curation

A GitHub Actions workflow is configured in [.github/workflows/daily-brief.yml](file:///Users/allistera/Development/Projects/Daily-News/.github/workflows/daily-brief.yml). It will automatically run code linting and type checks, and if those pass, curate and email the daily news briefing.

### Setup Instructions

1. Push your repository to GitHub.
2. In your GitHub repository, navigate to **Settings > Secrets and variables > Actions**.
3. Create the following **Repository Secrets**:
   - `ANTHROPIC_API_KEY`: Your Claude API Key
   - `RESEND_API_KEY`: Your Resend API Key
   - `USER_NAME`: Your name
   - `USER_EMAIL`: Recipient email address
   - `USER_INTERESTS`: Comma-separated interests (e.g. `AI advancements,World News,New Technology,Home tech`)
   - `USER_TONE`: Curation tone (optional)
   - `USER_PREFERENCES`: Summary filters (optional)
   - `SENDER_EMAIL`: Resend sender address (optional)
   - `CLAUDE_MODEL`: e.g. `claude-3-5-sonnet-latest` (optional)

---

## File Structure

- `src/`
  - `index.ts`: Public SDK Exports.
  - `sdk.ts`: Main orchestrator orchestrating the pipeline.
  - `types.ts`: TypeScript interfaces for configurations, articles, and newsletters.
  - `agents/`
    - `BaseAgent.ts`: Abstract base agent class.
    - `RSSAgent.ts`: Child agent for fetching & parsing RSS feeds.
    - `ScraperAgent.ts`: Child agent for website scraping with cheerio.
    - `PersonalizerAgent.ts`: Agent that coordinates with Claude for scoring and summarization.
    - `EmailAgent.ts`: Agent that sends emails via Resend.
  - `templates/`
    - `emailTemplate.ts`: Styled HTML templates.
- `examples/`
  - `daily_brief.ts`: Quick demonstration runner script.
