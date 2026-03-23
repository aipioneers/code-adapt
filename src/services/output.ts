import chalk from 'chalk';
import Table from 'cli-table3';
import ora from 'ora';

/**
 * Output data to stdout. If the json option is set, output as JSON.
 * Otherwise, output using a human-readable format.
 */
export function output(data: unknown, options: { json?: boolean } = {}): void {
  if (options.json) {
    process.stdout.write(JSON.stringify(data, null, 2) + '\n');
  } else if (typeof data === 'string') {
    process.stdout.write(data + '\n');
  } else {
    process.stdout.write(JSON.stringify(data, null, 2) + '\n');
  }
}

/**
 * Render a table to stdout using cli-table3.
 */
export function outputTable(headers: string[], rows: string[][]): void {
  const table = new Table({
    head: headers.map((h) => chalk.bold(h)),
    style: { head: [], border: [] },
  });

  for (const row of rows) {
    table.push(row);
  }

  process.stdout.write(table.toString() + '\n');
}

/**
 * Output a success message in green to stdout.
 */
export function outputSuccess(message: string): void {
  process.stdout.write(chalk.green(message) + '\n');
}

/**
 * Output a warning message in yellow to stdout.
 */
export function outputWarning(message: string): void {
  process.stdout.write(chalk.yellow(message) + '\n');
}

/**
 * Output an error message in red to stderr.
 */
export function outputError(message: string): void {
  process.stderr.write(chalk.red(message) + '\n');
}

/**
 * Wrap an async function with an ora spinner.
 * Shows the message while the function is running,
 * succeeds on completion, and fails on error.
 */
export async function withSpinner<T>(
  message: string,
  fn: () => Promise<T>,
): Promise<T> {
  const spinner = ora(message).start();
  try {
    const result = await fn();
    spinner.succeed();
    return result;
  } catch (err) {
    spinner.fail();
    throw err;
  }
}
