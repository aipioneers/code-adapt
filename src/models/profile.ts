export interface Profile {
  name: string;
  stack: string[];
  architecture: string;
  conventions: string[];
  criticalModules: string[];
  priorities: string[];
}

/**
 * Return a default profile seeded with the given project name.
 */
export function defaultProfile(name: string): Profile {
  return {
    name,
    stack: [],
    architecture: '',
    conventions: [],
    criticalModules: [],
    priorities: [],
  };
}
