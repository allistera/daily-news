import { Article } from '../types';

export abstract class BaseAgent {
  public id: string;
  public name: string;

  constructor(id: string, name: string) {
    this.id = id;
    this.name = name;
  }

  /**
   * Execute the agent's data harvesting job.
   * Returns a list of standardized Article objects.
   */
  abstract run(): Promise<Article[]>;
}
