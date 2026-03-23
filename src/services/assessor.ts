import type { Analysis } from '../models/analysis.js';
import type { Profile } from '../models/profile.js';
import type { Policy } from '../models/policy.js';
import type { RelevanceScore, RiskScore, SuggestedAction } from '../models/adaptation.js';

export interface AssessmentResult {
  relevance: RelevanceScore;
  riskScore: RiskScore;
  strategicValue: string;
  suggestedAction: SuggestedAction;
}

/**
 * Assess the relevance, risk, and suggested action for an analysis
 * given the downstream project's profile and policy.
 */
export function assessRelevance(
  analysis: Analysis,
  profile: Profile,
  policy: Policy,
): AssessmentResult {
  const relevance = computeRelevance(analysis, profile, policy);
  const riskScore = computeRisk(analysis);
  const suggestedAction = computeSuggestedAction(relevance, riskScore);
  const strategicValue = computeStrategicValue(analysis, profile);

  return { relevance, riskScore, strategicValue, suggestedAction };
}

/**
 * Relevance scoring:
 *   - affectedModules overlap with profile.criticalModules → high
 *   - affectedModules overlap with policy.relevantModules  → medium
 *   - affectedModules overlap with policy.ignoredModules   → low
 *   - default: medium
 */
function computeRelevance(
  analysis: Analysis,
  profile: Profile,
  policy: Policy,
): RelevanceScore {
  const modules = analysis.affectedModules;

  // Check critical modules first (highest priority)
  if (
    profile.criticalModules.length > 0 &&
    modules.some((m) => profile.criticalModules.includes(m))
  ) {
    return 'high';
  }

  // Check ignored modules (lowest priority — if everything is ignored, low relevance)
  if (
    policy.ignoredModules.length > 0 &&
    modules.every((m) => policy.ignoredModules.includes(m))
  ) {
    return 'low';
  }

  // Check relevant modules
  if (
    policy.relevantModules.length > 0 &&
    modules.some((m) => policy.relevantModules.includes(m))
  ) {
    return 'medium';
  }

  return 'medium';
}

/**
 * Risk scoring:
 *   - security classification → high
 *   - many files changed (>20) or many additions (>500) → high
 *   - moderate files changed (>5) → medium
 *   - default: low
 */
function computeRisk(analysis: Analysis): RiskScore {
  if (analysis.classification === 'security') {
    return 'high';
  }

  if (analysis.diffStats.filesChanged > 20 || analysis.diffStats.additions > 500) {
    return 'high';
  }

  if (analysis.diffStats.filesChanged > 5) {
    return 'medium';
  }

  return 'low';
}

/**
 * Suggested action based on relevance and risk:
 *   - high relevance + low risk  → adopt
 *   - high relevance + high risk → adapt-partially
 *   - medium relevance           → monitor
 *   - low relevance              → ignore
 */
function computeSuggestedAction(
  relevance: RelevanceScore,
  risk: RiskScore,
): SuggestedAction {
  if (relevance === 'high' && risk === 'low') {
    return 'adopt';
  }
  if (relevance === 'high' && risk === 'high') {
    return 'adapt-partially';
  }
  if (relevance === 'high') {
    // high relevance + medium risk
    return 'adopt';
  }
  if (relevance === 'medium') {
    return 'monitor';
  }
  return 'ignore';
}

/**
 * Compute strategic value from the overlap between analysis intent
 * and the profile's priorities.
 */
function computeStrategicValue(analysis: Analysis, profile: Profile): string {
  if (profile.priorities.length === 0) {
    return `Relevant ${analysis.classification} change in ${analysis.affectedModules.join(', ') || 'unknown modules'}.`;
  }

  const intentLower = analysis.intent.toLowerCase();
  const matchingPriorities = profile.priorities.filter((p) =>
    intentLower.includes(p.toLowerCase()),
  );

  if (matchingPriorities.length > 0) {
    return `Aligns with priorities: ${matchingPriorities.join(', ')}.`;
  }

  return `${analysis.classification.charAt(0).toUpperCase() + analysis.classification.slice(1)} change; review for alignment with project goals.`;
}
