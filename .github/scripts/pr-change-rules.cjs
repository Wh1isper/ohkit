// First matching category wins; no source execution is needed for classification.
const CORE = 'Python library';
const UI = 'Examples';
const categories = [CORE, UI, 'Tests & fixtures', 'Specifications', 'Documentation',
  'Build & CI', 'Developer tools', 'Dependencies & lockfiles', 'Unclassified'];
const rules = [
  ['Specifications', /^spec\//],
  ['Documentation', /\.md$|(?:^|\/)(?:LICENSE|NOTICE)$/i],
  ['Dependencies & lockfiles', /^(?:pyproject\.toml|uv\.lock)$/],
  ['Tests & fixtures', /(?:^|\/)tests\/|\.test\.cjs$/],
  ['Build & CI', /^\.github\/|^Makefile$|^\.[^/]+$/],
  ['Developer tools', /^(?:scripts|\.agents|\.claude)\//],
  [UI, /^examples\//],
  [CORE, /^ohkit\//],
];
function classify(path) {
  return rules.find(([, pattern]) => pattern.test(path))?.[0] || 'Unclassified';
}
function component(path) {
  return path.startsWith('ohkit/') || path.startsWith('tests/') ? 'ohkit' : 'Repository';
}
const icons = Object.fromEntries(categories.map(category => [category, '']));
module.exports = {CORE, UI, categories, icons, classify, component};
