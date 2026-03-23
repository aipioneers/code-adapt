import { ValidationError } from '../lib/errors.js';

export type AdaptationStatus =
  | 'observed'
  | 'analyzed'
  | 'assessed'
  | 'planned'
  | 'implemented'
  | 'validated'
  | 'contributed'
  | 'merged'
  | 'rejected';

export type RelevanceScore = 'high' | 'medium' | 'low';
export type RiskScore = 'high' | 'medium' | 'low';
export type SuggestedAction = 'adopt' | 'ignore' | 'monitor' | 'adapt-partially';
export type Strategy =
  | 'direct-adoption'
  | 'partial-reimplementation'
  | 'improved-implementation';

export interface Adaptation {
  id: string;
  sourceRepo: string;
  sourceRef: string;
  sourceRefType: 'pr' | 'commit' | 'release';
  analysisId: string | null;
  status: AdaptationStatus;
  relevance: RelevanceScore | null;
  riskScore: RiskScore | null;
  suggestedAction: SuggestedAction | null;
  strategy: Strategy | null;
  targetModules: string[];
  planId: string | null;
  branch: string | null;
  createdAt: string;
  updatedAt: string;
}

/**
 * Valid state transitions for an Adaptation entity.
 */
const VALID_TRANSITIONS: Record<AdaptationStatus, AdaptationStatus[]> = {
  observed: ['analyzed', 'planned', 'rejected'],
  analyzed: ['assessed', 'planned', 'rejected'],
  assessed: ['planned', 'rejected'],
  planned: ['implemented', 'rejected'],
  implemented: ['validated', 'rejected'],
  validated: ['contributed', 'merged', 'rejected'],
  contributed: ['merged', 'rejected'],
  merged: [],
  rejected: [],
};

/**
 * Check whether a transition from one status to another is valid.
 */
export function canTransition(from: AdaptationStatus, to: AdaptationStatus): boolean {
  return VALID_TRANSITIONS[from].includes(to);
}

/**
 * Transition an Adaptation to a new status, returning an updated copy.
 * Throws ValidationError if the transition is not allowed.
 */
export function transitionStatus(adaptation: Adaptation, to: AdaptationStatus): Adaptation {
  if (!canTransition(adaptation.status, to)) {
    throw new ValidationError(
      `Invalid status transition: "${adaptation.status}" → "${to}". ` +
        `Allowed transitions: ${VALID_TRANSITIONS[adaptation.status].join(', ') || 'none'}.`,
    );
  }

  return {
    ...adaptation,
    status: to,
    updatedAt: new Date().toISOString(),
  };
}
