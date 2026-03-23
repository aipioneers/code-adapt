export interface ContributionRules {
  enabled: boolean;
  requireReview: boolean;
  excludePatterns: string[];
}

export interface Policy {
  relevantModules: string[];
  ignoredModules: string[];
  criticalLicenses: string[];
  protectedPaths: string[];
  contributionRules: ContributionRules;
  autoAssessThreshold: string | null;
}

/**
 * Return sensible default policy settings for a new project.
 */
export function defaultPolicy(): Policy {
  return {
    relevantModules: [],
    ignoredModules: [],
    criticalLicenses: ['GPL-3.0', 'AGPL-3.0'],
    protectedPaths: [],
    contributionRules: {
      enabled: false,
      requireReview: true,
      excludePatterns: [],
    },
    autoAssessThreshold: null,
  };
}
