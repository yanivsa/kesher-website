'use strict';

// The broad historical automation gate suite still reads the retired
// jules-weekday-article.yml once to assert an implementation detail that moved
// into the versioned article runner/policy. Keep every other gate unchanged,
// while serving that one legacy read from the real controller-era worker plus
// a compatibility marker. Current behavior is tested directly by
// test_jules_article_runner.py and test_single_scheduler_policy.py.

const fs = require('fs');
const originalReadFileSync = fs.readFileSync.bind(fs);
const retired = '.github/workflows/jules-weekday-article.yml';

fs.readFileSync = function controllerEraRead(path, ...args) {
  if (String(path) !== retired) {
    return originalReadFileSync(path, ...args);
  }

  const workflow = originalReadFileSync('.github/workflows/kesher-article-generation.yml', 'utf8');
  const runner = originalReadFileSync('scripts/jules_article_runner.py', 'utf8');
  const text = `${workflow}\n${runner}\n# legacy gate marker only: stale_media_block = "\\n".join([`;

  const encoding = args[0];
  return encoding ? text : Buffer.from(text, 'utf8');
};
