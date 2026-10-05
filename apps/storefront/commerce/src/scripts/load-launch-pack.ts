import { readFileSync } from "node:fs";
import { summarizeLaunchLoad } from "../launch-load";

const file = process.argv[2];
const pack = file ? JSON.parse(readFileSync(file, "utf8")) as unknown : undefined;
const summary = summarizeLaunchLoad(pack);
console.log(JSON.stringify(summary, null, 2));
if (!summary.loaded) process.exitCode = 1;
