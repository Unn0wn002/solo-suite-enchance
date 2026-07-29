import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";

const root = resolve(process.argv[2] || ".");
const manifest = JSON.parse(
  readFileSync(resolve(root, "core-tooling.json"), "utf8"),
);

function available(command, args) {
  try {
    const executable =
      process.platform === "win32" && ["npx", "npm"].includes(command)
        ? `${command}.cmd`
        : command;
    if (process.platform === "win32" && executable.endsWith(".cmd")) {
      execFileSync("cmd.exe", ["/d", "/s", "/c", `${executable} ${args.join(" ")}`], {
        stdio: "ignore",
        windowsHide: true,
      });
    } else {
      execFileSync(executable, args, { stdio: "ignore", windowsHide: true });
    }
    return true;
  } catch {
    return false;
  }
}

let missing = 0;
for (const tool of manifest.tools) {
  const [command, ...args] = tool.verify.split(" ");
  const ok = available(command, args);
  const optional = tool.availability === "optional";
  const label = ok ? "PASS" : optional ? "OPTIONAL_MISSING" : "MISSING";
  console.log(`${label} ${tool.name}: ${tool.verify}`);
  if (!ok && !optional) missing += 1;
}

if (missing > 0) {
  console.log(`Optional core tooling missing: ${missing}. See CORE_REPOSITORY_INTELLIGENCE.md.`);
  process.exitCode = 1;
} else {
  console.log("All required repository-intelligence commands are available.");
}
