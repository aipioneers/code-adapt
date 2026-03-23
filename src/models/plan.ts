export interface PlanStep {
  order: number;
  description: string;
  targetFile: string;
  type: 'create' | 'modify' | 'delete' | 'test';
}

export interface ContributionSplit {
  upstream: string[];
  internal: string[];
}

export interface Plan {
  id: string;
  adaptationId: string;
  strategy: string;
  targetModules: string[];
  steps: PlanStep[];
  dependencies: string[];
  suggestedTests: string[];
  contributionSplit: ContributionSplit | null;
  createdAt: string;
}
