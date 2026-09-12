import { readFileSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
const config = "dist/server/wrangler.json";
if (!existsSync(config))
  throw new Error("Build first to generate local binding configuration");
const journal = JSON.parse(readFileSync("drizzle/meta/_journal.json", "utf8"));
// Wrangler records migrations applied through migrations apply. Assemble the
// same generated SQL into a temporary migration directory, preserving order.
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
const directory = mkdtempSync(join(tmpdir(), "constellation-migrations-"));
try {
  for (const entry of journal.entries)
    writeFileSync(
      join(directory, entry.tag + ".sql"),
      readFileSync("drizzle/" + entry.tag + ".sql"),
    );
  const source = JSON.parse(readFileSync(config, "utf8"));
  // Bindings use the standard local state directory and Wrangler's migration ledger.
  const local = {
    name: "constellation-local-migrations",
    compatibility_date: "2026-05-15",
    d1_databases: source.d1_databases.map((binding) => ({
      ...binding,
      migrations_dir: directory,
    })),
  };
  const localConfig = join(directory, "wrangler.json");
  writeFileSync(localConfig, JSON.stringify(local));
  const r = spawnSync(
    process.execPath,
    [
      "--import",
      "./scripts/sites-env.mjs",
      "./node_modules/wrangler/bin/wrangler.js",
      "d1",
      "migrations",
      "apply",
      "DB",
      "--local",
      "--config",
      localConfig,
      "--persist-to",
      resolve(process.argv[2] || ".wrangler/state"),
    ],
    { stdio: "inherit" },
  );
  if (r.status !== 0) process.exitCode = r.status || 1;
} finally {
  rmSync(directory, { recursive: true, force: true });
}
