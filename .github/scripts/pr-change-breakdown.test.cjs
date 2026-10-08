const test = require('node:test');
const assert = require('node:assert/strict');
const {classify, CORE} = require('./pr-change-rules.cjs');
const {report, publish} = require('./pr-change-breakdown.cjs');
const pr = {number: 1, state: 'open', changed_files: 1, html_url: 'https://github.com/converge-ai-labs/ohkit/pull/1', head: {sha: 'head'}, base: {sha: 'base'}};
const file = {filename: 'ohkit/__init__.py', additions: 2, deletions: 1, status: 'modified'};

test('classify package, tests, docs, lock, and automation', () => {
  for (const [path, expected] of [['ohkit/__init__.py', CORE], ['scripts/tests/test_release.py', 'Tests & fixtures'], ['spec/README.md', 'Specifications'], ['README.md', 'Documentation'], ['uv.lock', 'Dependencies & lockfiles'], ['.github/workflows/ci.yml', 'Build & CI']]) assert.equal(classify(path), expected);
});
test('report core changes and incomplete pagination honestly', () => {
  assert.match(report(pr, [file]), /Python library/);
  assert.match(report({...pr, changed_files: 2}, [file]), /Incomplete report/);
});
test('escape untrusted paths and mentions', () => {
  const body = report(pr, [{...file, filename: 'ohkit/<script>@all|.py'}]);
  assert.ok(!body.includes('<script>'));
  assert.ok(!body.includes('@all'));
});
test('do not publish a report after a head change', async () => {
  let calls = 0;
  let writes = 0;
  const github = {rest: {pulls: {get: async () => ({data: ++calls === 1 ? pr : {...pr, head: {sha: 'new'}}}), listFiles: 'files'}, issues: {listComments: 'comments', createComment: async () => {writes++;}}}, paginate: async method => method === 'files' ? [file] : []};
  await publish({github, context: {repo: {owner: 'o', repo: 'r'}, payload: {pull_request: pr}}, core: {notice() {}}});
  assert.equal(writes, 0);
});
