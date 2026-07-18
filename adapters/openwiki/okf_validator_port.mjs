// Verbatim JS port of OpenWiki's validateOkfFrontmatter (src/agent/frontmatter-validator.ts
// @ d4e94ab) — types stripped, logic identical. Validates corpus-orienteer's emitted pages.
import { parse } from "yaml";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const OKF_STRING_FIELDS = ["type", "title", "description", "resource"];
const OKF_FIELDS = new Set([...OKF_STRING_FIELDS, "tags"]);
const issue = (code, message, line) => ({ code, message, ...(line ? { line } : {}) });
const invalid = (code, message, line) => ({ issues: [issue(code, message, line)], valid: false });
const isRecord = (v) => typeof v === "object" && v !== null && !Array.isArray(v);

function validateOkfFrontmatter(content) {
  const lines = content.split(/\r?\n/u);
  if (lines[0] !== "---") return invalid("missing_opening_delimiter", "File must begin with `---`.", 1);
  const closingLine = lines.indexOf("---", 1);
  if (closingLine === -1) return invalid("missing_closing_delimiter", "Opening front matter has no closing `---` delimiter.");
  let fields;
  try {
    fields = parse(`\n${lines.slice(1, closingLine).join("\n")}`, { maxAliasCount: 100, schema: "core", uniqueKeys: true });
  } catch (e) { return invalid("invalid_yaml", String(e && e.message || e)); }
  if (!isRecord(fields)) return invalid("invalid_yaml_root", "Front matter must be a YAML mapping.");
  const issues = Object.keys(fields).filter((k) => !OKF_FIELDS.has(k))
    .map((k) => issue("unsupported_field", `Unsupported field \`${k}\`.`));
  if (!Object.hasOwn(fields, "type")) issues.push(issue("missing_type", "Required field `type` is missing."));
  for (const f of OKF_STRING_FIELDS)
    if (Object.hasOwn(fields, f) && (typeof fields[f] !== "string" || !fields[f].trim()))
      issues.push(issue(`invalid_${f}`, `Field \`${f}\` must be a non-empty string.`));
  if (Object.hasOwn(fields, "tags") && (!Array.isArray(fields.tags) || fields.tags.some((t) => typeof t !== "string" || !t.trim())))
    issues.push(issue("invalid_tags", "Field `tags` must be a YAML list of non-empty strings."));
  return issues.length === 0 ? { valid: true } : { issues, valid: false };
}

const dir = process.argv[2];
let bad = 0;
for (const f of readdirSync(dir).filter((f) => f.endsWith(".md")).sort()) {
  const v = validateOkfFrontmatter(readFileSync(join(dir, f), "utf8"));
  console.log(`${f}: ${v.valid ? "VALID" : "INVALID " + JSON.stringify(v.issues)}`);
  if (!v.valid) bad++;
}
process.exit(bad ? 1 : 0);
