export interface LearningRecord {
  adaptationId: string;
  outcome: 'accepted' | 'rejected';
  reason: string | null;
  recordedAt: string; // ISO 8601
}
