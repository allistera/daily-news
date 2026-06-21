import * as dotenv from 'dotenv';
import { ClaudeNewsSDK } from '../src';
import * as path from 'path';

// Load environment variables from .env file
dotenv.config({ path: path.resolve(__dirname, '../.env') });

async function main() {
  const anthropicApiKey = process.env.ANTHROPIC_API_KEY;
  const resendApiKey = process.env.RESEND_API_KEY;
  const userEmail = process.env.USER_EMAIL || 'alex@example.com';
  const userName = process.env.USER_NAME || 'Alex';
  
  // Parse interests from string list
  const interests = process.env.USER_INTERESTS
    ? process.env.USER_INTERESTS.split(',')
    : ['Artificial Intelligence', 'TypeScript', 'Web Development', 'Space Exploration'];

  if (!anthropicApiKey || !resendApiKey) {
    console.error('ERROR: ANTHROPIC_API_KEY and RESEND_API_KEY must be set in your .env file.');
    console.log('\nPlease create a .env file based on .env.example and populate the keys.');
    process.exit(1);
  }

  console.log('--- Initializing Claude News SDK Example ---');

  // Initialize the orchestrator SDK
  const sdk = new ClaudeNewsSDK({
    anthropicApiKey,
    resendApiKey,
    fromEmail: process.env.SENDER_EMAIL,
    model: process.env.CLAUDE_MODEL,
    userProfile: {
      name: userName,
      email: userEmail,
      interests: interests,
      tone: process.env.USER_TONE || 'informative and engaging',
      additionalPreferences: process.env.USER_PREFERENCES
    }
  });

  // Load sources from central sources.json config file
  sdk.loadSourcesFromJson(path.resolve(__dirname, '../sources.json'));

  try {
    const result = await sdk.run();
    
    console.log('\n--- SUCCESS ---');
    console.log(`Newsletter Title: "${result.newsletter.title}"`);
    console.log(`Date: ${result.newsletter.date}`);
    console.log(`Intro: "${result.newsletter.intro.substring(0, 120)}..."`);
    
    console.log('\nSections and Articles compiled:');
    result.newsletter.sections.forEach(section => {
      console.log(`\n📂 [${section.category}] - ${section.description || ''}`);
      section.articles.forEach(art => {
        console.log(`  - [Match: ${art.relevanceScore}/10] ${art.title} (${art.sourceName})`);
        console.log(`    Link: ${art.link}`);
        console.log(`    Why: "${art.relevanceExplanation}"`);
      });
    });

    console.log(`\nSent Email via Resend. Dispatch ID: ${result.emailId}`);
    
  } catch (error) {
    console.error('\nPipeline execution failed:', error);
  }
}

main();
