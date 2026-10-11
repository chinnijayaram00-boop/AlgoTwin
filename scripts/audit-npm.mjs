#!/usr/bin/env node
// Dependency vulnerability gate for the npm workspace.
//
// `npm audit` exits non-zero as soon as *any* advisory is present, so on its own
// it cannot express a threshold: a low-severity advisory in a dev-only tool
// fails a build just as hard as a critical one in shipped code. This wrapper
// makes the policy explicit and auditable instead of silencing it:
//
//   * it fails the run when a vulnerability of at least `--threshold` severity
//     (default: high) exists and is not deliberately accepted, and
//   * it *prints* every accepted (ignored) advisory and every finding below the
//     threshold, so nothing is hidden -- accepting one is always visible.
//
// Ignoring is opt-in and must be passed on the command line, so an accepted
// advisory lives in a reviewable diff in `.github/workflows/ci.yml` and, locally,
// in the command a developer runs. The argument is `<id>@<severity>#<reason>`,
// where `<id>` is the vulnerability key from `npm audit` (the package name or an
// advisory id), `<severity>` is the level it was accepted at, and `<reason>` is
// free text. The id may repeat; every acceptance is printed.
//
// Usage:
//   node scripts/audit-npm.mjs [--threshold=high] [--json=FILE] [--ignore=ID@SEV#REASON ...]
//
// Exits 0 when nothing meets the threshold, 1 when the gate fails, 2 on a usage
// or tooling error (so "the scanner broke" never looks like "no vulnerabilities").

import { spawnSync } from "node:child_process";
import { writeFileSync } from "node:fs";

const LEVELS = ["info", "low", "moderate", "high", "critical"];

function parseArgs(argv) {
  const options = { threshold: "high", jsonPath: "", ignores: [] };
  for (const arg of argv) {
    if (arg.startsWith("--threshold=")) {
      options.threshold = arg.slice("--threshold=".length);
    } else if (arg.startsWith("--json=")) {
      options.jsonPath = arg.slice("--json=".length);
    } else if (arg.startsWith("--ignore=")) {
      options.ignores.push(parseIgnore(arg.slice("--ignore=".length)));
    } else {
      throw new Error(`unknown argument: ${arg}`);
    }
  }
  if (!LEVELS.includes(options.threshold)) {
    throw new Error(`--threshold must be one of ${LEVELS.join(", ")}`);
  }
  return options;
}

function parseIgnore(spec) {
  const [idAndSeverity, ...reasonParts] = spec.split("#");
  const reason = reasonParts.join("#").trim();
  const at = idAndSeverity.lastIndexOf("@");
  if (at <= 0) {
    throw new Error(`--ignore expects ID@SEVERITY#REASON, got: ${spec}`);
  }
  const id = idAndSeverity.slice(0, at);
  const severity = idAndSeverity.slice(at + 1);
  if (!LEVELS.includes(severity)) {
    throw new Error(`--ignore severity must be one of ${LEVELS.join(", ")}: ${spec}`);
  }
  return { id, severity, reason: reason || "(no reason given)" };
}

function run() {
  const options = parseArgs(process.argv.slice(2));

  if (options.jsonPath) {
    writeFileSync(options.jsonPath, "", "utf8");
  }

  const npm = process.platform === "win32" ? "npm.cmd" : "npm";
  const result = spawnSync(npm, ["audit", "--json"], {
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
    // Windows ships `npm` as a `.cmd` shim, which Node 18.20+/20.12+/22 refuses
    // to spawn without a shell; the arguments here are fixed, so there is no
    // injection surface.
    shell: process.platform === "win32",
  });
  // `npm audit` writes the report to stdout and exits 1 when advisories exist;
  // only a missing report is a tooling failure.
  const raw = result.stdout || "";
  if (!raw.trim()) {
    console.error("npm audit produced no report; run `npm install` and retry.");
    if (result.stderr) {
      console.error(result.stderr.trim());
    }
    process.exit(2);
  }

  let report;
  try {
    report = JSON.parse(raw);
  } catch {
    console.error("Could not parse the npm audit report as JSON.");
    process.exit(2);
  }

  if (options.jsonPath) {
    writeFileSync(options.jsonPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  }

  const vulnerabilities = report.vulnerabilities ?? {};
  const counts = report.metadata?.vulnerabilities ?? {};
  const printCounts = LEVELS.map((level) => `${counts[level] ?? 0} ${level}`).join(", ");
  console.log(`npm audit: ${counts.total ?? 0} advisories (${printCounts})`);

  const thresholdRank = LEVELS.indexOf(options.threshold);
  const accepted = new Map();
  for (const ignore of options.ignores) {
    if (!accepted.has(ignore.id)) {
      accepted.set(ignore.id, []);
    }
    accepted.get(ignore.id).push(ignore);
  }

  const below = [];
  const blocking = [];
  const ignored = [];

  for (const [name, details] of Object.entries(vulnerabilities)) {
    const severity = details.severity ?? "info";
    const rank = LEVELS.indexOf(severity);
    if (rank < thresholdRank) {
      below.push(`${name} (${severity})`);
      continue;
    }
    const acceptance = accepted.get(name);
    if (acceptance) {
      for (const entry of acceptance) {
        ignored.push(`${name} (${severity}) -- accepted at ${entry.severity}: ${entry.reason}`);
      }
      continue;
    }
    const via = (details.via ?? [])
      .map((item) => (typeof item === "string" ? item : item.title ?? item.url ?? "?"))
      .join("; ");
    blocking.push(`${name} (${severity}) via ${via || "?"}`);
  }

  if (below.length > 0) {
    console.log(`\nBelow the "${options.threshold}" threshold (informational, not blocking):`);
    for (const line of below) {
      console.log(`  - ${line}`);
    }
  }
  if (ignored.length > 0) {
    console.log("\nAccepted advisories (explicitly ignored):");
    for (const line of ignored) {
      console.log(`  - ${line}`);
    }
  }

  if (blocking.length > 0) {
    console.error(
      `\n${blocking.length} advis${blocking.length === 1 ? "ory" : "ories"} at or above "${options.threshold}"`,
    );
    for (const line of blocking) {
      console.error(`  - ${line}`);
    }
    console.error("\nFix by upgrading, or accept with a documented --ignore in the CI workflow.");
    process.exit(1);
  }

  const total = counts.total ?? Object.keys(vulnerabilities).length;
  console.log(`\nNo unaccepted advisories at or above "${options.threshold}" (${total} advisories examined).`);
}

try {
  run();
} catch (error) {
  console.error(`audit-npm: ${error.message}`);
  process.exit(2);
}
