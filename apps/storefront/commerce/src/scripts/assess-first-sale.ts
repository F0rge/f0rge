import { readFileSync } from "node:fs";
import { assessFirstSaleReadiness } from "../first-sale-readiness";

const file = process.argv[2];
const evidence = file ? JSON.parse(readFileSync(file, "utf8")) as unknown : undefined;
const summary = assessFirstSaleReadiness(evidence);
console.log(JSON.stringify(summary, null, 2));
if (summary.decision !== "go" || summary.public_selling !== false) process.exitCode = 1;
