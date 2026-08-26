// Turn node's coverage summary into the cobertura line-rate the contract reads.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
mkdirSync("reports", { recursive: true });
const text = readFileSync("reports/cov.txt", "utf8");
const row = text.split("\n").find((l) => l.includes("all files"));
const pct = row ? Number(row.split("|")[1].trim()) : 0;
const valid = 100, covered = Math.round(pct);
writeFileSync(
  "reports/coverage.xml",
  `<?xml version="1.0"?>\n<coverage line-rate="${(pct / 100).toFixed(4)}" lines-valid="${valid}" lines-covered="${covered}"/>\n`
);
console.log(`coverage ${pct}%`);
