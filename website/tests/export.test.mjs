import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const read = (path) =>
  readFileSync(new URL(`../out/${path}`, import.meta.url), "utf8");
const routes = [
  "",
  "getting-started/",
  "examples/application-hosted-executor/",
  "documentation/",
  "releasing/",
];

for (const route of routes) {
  test(`preserves the public route /${route}`, () => {
    const html = read(`${route}index.html`);
    assert.match(html, /<html[^>]*lang="en"/);
    assert.ok(
      html.includes(
        `<link rel="canonical" href="https://ohkit.wh1isper.top/${route}"`,
      ),
    );
    for (const [, href] of html.matchAll(/<a\s[^>]*href="([^"]+)"/g)) {
      if (!/^https?:/.test(href)) assert.doesNotMatch(href, /\.md(?:#|$|\?)/);
    }
  });
}

test("search index is exported with documentation content", () => {
  const index = JSON.parse(read("api/search"));
  const text = JSON.stringify(index);
  assert.match(text, /Application-hosted executor/);
  assert.match(text, /Workspace/);
});

test("bootstrap limitations remain visible", () => {
  assert.match(read("index.html"), /version metadata only/);
  assert.match(read("getting-started/index.html"), /does not yet run Codex/);
  const example = read("examples/application-hosted-executor/index.html");
  assert.match(example, /Design example, not a shipped API/);
  assert.match(example, /View Mermaid source/);
  assert.match(example, /Expand/);
});

test("every source page and navigation entry has an exported destination", () => {
  const docs = fileURLToPath(new URL("../../docs/", import.meta.url));
  function visit(dir, prefix = "") {
    const entries = readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory())
        visit(join(dir, entry.name), `${prefix}${entry.name}/`);
      if (entry.name.endsWith(".md")) {
        const name = entry.name.slice(0, -3);
        read(`${prefix}${name === "index" ? "" : `${name}/`}index.html`);
      }
      if (entry.name === "meta.json") {
        const meta = JSON.parse(readFileSync(join(dir, entry.name), "utf8"));
        for (const page of meta.pages) {
          if (page.startsWith("---")) continue;
          assert.ok(
            entries.some(
              (item) => item.name === page || item.name === `${page}.md`,
            ),
            `Unknown navigation entry: ${prefix}${page}`,
          );
        }
      }
    }
  }
  visit(docs);
});
