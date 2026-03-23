export interface DiffStats {
  additions: number;
  deletions: number;
  filesChanged: number;
}

export interface Analysis {
  id: string;
  observationId: string | null;
  sourceRef: string;
  sourceRefType: 'pr' | 'commit' | 'release';
  repoName: string;
  summary: string;
  classification: 'feature' | 'bugfix' | 'refactor' | 'security' | 'unknown';
  intent: string;
  affectedFiles: string[];
  affectedModules: string[];
  diffStats: DiffStats;
  createdAt: string;
}
