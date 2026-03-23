import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import * as crypto from 'node:crypto';
import yaml from 'js-yaml';

/**
 * Read and parse a YAML file. Returns the parsed content typed as T.
 * Throws if the file does not exist.
 */
export function readYaml<T>(filePath: string): T {
  const content = fs.readFileSync(filePath, 'utf-8');
  return yaml.load(content) as T;
}

/**
 * Serialize data to YAML and write it to a file atomically
 * (write to temp file, then rename).
 */
export function writeYaml(filePath: string, data: unknown): void {
  const content = yaml.dump(data, { noRefs: true, lineWidth: -1 });
  atomicWrite(filePath, content);
}

/**
 * Read and parse a JSON file. Returns the parsed content typed as T.
 * Throws if the file does not exist.
 */
export function readJson<T>(filePath: string): T {
  const content = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(content) as T;
}

/**
 * Serialize data to pretty-printed JSON and write it to a file atomically
 * (write to temp file, then rename).
 */
export function writeJson(filePath: string, data: unknown): void {
  const content = JSON.stringify(data, null, 2) + '\n';
  atomicWrite(filePath, content);
}

/**
 * Check if a file exists at the given path.
 */
export function exists(filePath: string): boolean {
  return fs.existsSync(filePath);
}

/**
 * Write content to a file atomically by writing to a temporary file
 * in the same directory and then renaming it.
 */
function atomicWrite(filePath: string, content: string): void {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });

  const tmpFile = path.join(
    dir,
    `.tmp-${crypto.randomBytes(6).toString('hex')}`,
  );

  try {
    fs.writeFileSync(tmpFile, content, 'utf-8');
    fs.renameSync(tmpFile, filePath);
  } catch (err) {
    // Clean up temp file on failure
    try {
      fs.unlinkSync(tmpFile);
    } catch {
      // Ignore cleanup errors
    }
    throw err;
  }
}
