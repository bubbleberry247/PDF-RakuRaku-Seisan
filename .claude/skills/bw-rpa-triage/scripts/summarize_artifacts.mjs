#!/usr/bin/env node
/**
 * Artifact Summary Script
 *
 * Usage:
 *   node summarize_artifacts.mjs <artifact-folder-path>
 *   node summarize_artifacts.mjs artifacts/rakuraku-expense/20260214-160000-abc123
 *
 * Output:
 *   - File list with sizes
 *   - metadata.json key fields
 *   - Last 20 lines of execution.log
 *   - Recommendations for next steps
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// CLI argument
const artifactPath = process.argv[2];

if (!artifactPath) {
  console.error('Usage: node summarize_artifacts.mjs <artifact-folder-path>');
  process.exit(1);
}

// Resolve path
const fullPath = path.isAbsolute(artifactPath)
  ? artifactPath
  : path.resolve(process.cwd(), artifactPath);

if (!fs.existsSync(fullPath)) {
  console.error(`Error: Directory not found: ${fullPath}`);
  process.exit(1);
}

console.log(`Artifact Summary for: ${path.basename(fullPath)}`);
console.log('='.repeat(50));
console.log(`Directory: ${fullPath}\n`);

// Files to check
const expectedFiles = [
  'metadata.json',
  'execution.log',
  'trace.zip',
  'screenshots',
  'videos',
  'network/trace.har',
  'input/hash.txt',
  'input/sample.json',
  'output',
  'dump'
];

console.log('Files Found:');
for (const file of expectedFiles) {
  const filePath = path.join(fullPath, file);
  const exists = fs.existsSync(filePath);
  const symbol = exists ? '✓' : '✗';

  if (exists) {
    const stats = fs.statSync(filePath);
    if (stats.isDirectory()) {
      const files = fs.readdirSync(filePath);
      console.log(`  ${symbol} ${file}/ (${files.length} files)`);
    } else {
      const sizeKB = (stats.size / 1024).toFixed(0);
      const sizeMB = (stats.size / 1024 / 1024).toFixed(1);
      const sizeStr = stats.size > 1024 * 1024 ? `${sizeMB} MB` : `${sizeKB} KB`;
      console.log(`  ${symbol} ${file} (${sizeStr})`);
    }
  } else {
    console.log(`  ${symbol} ${file} (NOT FOUND)`);
  }
}

// Read metadata.json
const metadataPath = path.join(fullPath, 'metadata.json');
if (fs.existsSync(metadataPath)) {
  console.log('\nKey Metadata:');
  const metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf-8'));

  console.log(`  Status: ${metadata.status || 'unknown'}`);
  if (metadata.error) {
    console.log(`  Error Type: ${metadata.error.type || 'unknown'}`);
    console.log(`  Error Message: ${metadata.error.message || 'N/A'}`);
    console.log(`  Failed Step: ${metadata.error.step || 'N/A'}`);
  }
  console.log(`  Retry Count: ${metadata.retryCount || 0}`);
  console.log(`  Duration: ${metadata.duration || 'N/A'} ms`);
  console.log(`  Start: ${metadata.startTime || 'N/A'}`);
  console.log(`  End: ${metadata.endTime || 'N/A'}`);

  if (metadata.environment) {
    console.log(`  OS: ${metadata.environment.os || 'N/A'}`);
    console.log(`  Node: ${metadata.environment.nodeVersion || 'N/A'}`);
    console.log(`  Playwright: ${metadata.environment.playwrightVersion || 'N/A'}`);
  }
} else {
  console.log('\nKey Metadata: (NOT FOUND)');
}

// Read last 20 lines of execution.log
const logPath = path.join(fullPath, 'execution.log');
if (fs.existsSync(logPath)) {
  console.log('\nLog Summary (last 20 lines):');
  const logContent = fs.readFileSync(logPath, 'utf-8');
  const lines = logContent.split('\n').filter(line => line.trim());
  const last20 = lines.slice(-20);

  for (const line of last20) {
    // Extract level and message (assuming TSV format)
    const parts = line.split('\t');
    if (parts.length >= 4) {
      const [, level, stepId, message] = parts;
      console.log(`  [${level}] [${stepId}] ${message}`);
    } else {
      console.log(`  ${line}`);
    }
  }
} else {
  console.log('\nLog Summary: (NOT FOUND)');
}

// Recommendations
console.log('\nRecommendation:');
const hasTrace = fs.existsSync(path.join(fullPath, 'trace.zip'));
const hasScreenshots = fs.existsSync(path.join(fullPath, 'screenshots'));
const hasNetwork = fs.existsSync(path.join(fullPath, 'network/trace.har'));

if (hasTrace) {
  console.log('  - Trace.zip available → Use Playwright Trace Viewer');
  console.log('    Command: npx playwright show-trace ' + path.join(fullPath, 'trace.zip'));
}

if (hasScreenshots) {
  const screenshots = fs.readdirSync(path.join(fullPath, 'screenshots'));
  console.log(`  - Screenshots: ${screenshots.length} files → Check for UI changes`);
  for (const screenshot of screenshots) {
    console.log(`    - ${screenshot}`);
  }
}

if (hasNetwork) {
  const harSize = fs.statSync(path.join(fullPath, 'network/trace.har')).size;
  const harSizeMB = (harSize / 1024 / 1024).toFixed(1);
  console.log(`  - Network HAR: ${harSizeMB}MB → Check for API failures`);
}

console.log('\nNext Steps:');
console.log('  1. Review metadata.json for error details');
console.log('  2. Check execution.log for context around failure');
console.log('  3. Open screenshots to identify UI changes');
if (hasTrace) {
  console.log('  4. Analyze trace.zip with Playwright Trace Viewer');
}
if (hasNetwork) {
  console.log('  5. Review network/trace.har for API issues');
}
