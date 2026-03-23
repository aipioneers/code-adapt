export interface CommitSummary {
  sha: string;
  message: string;
  author: string;
  date: string;
}

export interface PRSummary {
  number: number;
  title: string;
  state: string;
  author: string;
  url: string;
}

export interface ReleaseSummary {
  tag: string;
  name: string;
  date: string;
  url: string;
}

export interface SecurityAlert {
  id: string;
  severity: string;
  summary: string;
}

export interface Observation {
  id: string;
  repoName: string;
  timestamp: string;
  since: string | null;
  commits: CommitSummary[];
  pullRequests: PRSummary[];
  releases: ReleaseSummary[];
  securityAlerts: SecurityAlert[];
}
