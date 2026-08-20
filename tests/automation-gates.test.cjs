const assert = require('assert');
const { execFileSync } = require('child_process');
const fs = require('fs');

function read(path) {
  return fs.readFileSync(path, 'utf8');
}

function testControllerHardening() {
  const articlePolicy = read('.github/prompts/jules-weekday-article-update.md');
  for (const path of [
    '.github/workflows/jules-daily-seo-geo-review.yml',
    '.github/workflows/jules-daily-mobile-review.yml',
    '.github/workflows/jules-nightly-site-fixes.yml',
    '.github/workflows/jules-daily-industry-benchmarking.yml',
    '.github/workflows/jules-weekly-content-review.yml',
  ]) {
    const workflow = read(path);
    assert(workflow.includes('strictly defined as a couples counselor'), `${path} must define the professional role`);
    assert(workflow.includes('family mediation (גישור)'), `${path} must retain the mediation exclusion`);
  }
  assert(!articlePolicy.includes('מגשרת מוסמכת'));
  assert(!articlePolicy.includes('עורכת דין בהכשרתה'));
  assert(articlePolicy.includes('אין להוסיף, לשנות או להתייחס לגירושין, שירותים משפטיים'));
}

function testContentValidatorContracts() {
  const validator = read('scripts/validate-content.cjs');
  assert(validator.includes('Post summaries are stale or incomplete; run npm run generate after the final posts.json edit.'));
  assert(validator.includes('const visibleProse = `${post.title}\\n${post.excerpt}\\n${stripHtml(post.content)}`'));
  assert(validator.includes('if (i === 0)'));
  for (const phrase of [
    'זה קורה כמעט לכל מי', 'טבעית לחלוטין', 'הצעד הראשון להתמודדות',
    'המלכודת הגדולה ביותר', 'הקצב שלכם הוא הקצב שלכם', 'אין לוח זמנים אוניברסלי',
    'מלאים ושלמים יותר', 'זירת התגוששות', 'שדה מוקשים', 'לנווט את התקופה',
    'הבנה עמוקה', 'חיבור אמיתי',
  ]) {
    assert(validator.includes(`"${phrase}"`), `Missing observed phrase guard: ${phrase}`);
  }
}

function testTrustedArticleImageV2() {
  const workflow = read('.github/workflows/kesher-article-image.yml');
  const worker = read('.github/scripts/article-image-worker.py');
  const gate = read('.github/scripts/validate-article-pr.py');
  const generation = read('.github/workflows/kesher-article-generation.yml');
  const runner = read('scripts/jules_article_runner_v3.py');
  const contract = JSON.parse(read('config/kesher-production-contract.json'));

  assert.strictEqual(contract.retry.max_attempts_per_stage, 3);
  assert.deepStrictEqual(contract.retry.backoff_minutes, [5, 15]);
  assert.strictEqual(contract.image.required_for_article, true);
  assert.strictEqual(contract.image.no_image_publication_allowed, false);
  assert.strictEqual(contract.image.worker_attempts_per_dispatch, 1);
  assert.strictEqual(contract.image.max_attempts, 3);
  assert.deepStrictEqual(contract.image.provider_order, ['gemini', 'unsplash', 'pexels', 'local-curated']);
  assert.strictEqual(contract.image.gemini_model, 'gemini-3.1-flash-image');

  assert(workflow.includes('pull_request_target:'));
  assert(workflow.includes('Checkout trusted image worker'));
  assert(workflow.includes('ref: main'));
  assert(workflow.includes('persist-credentials: false'));
  assert(workflow.includes('GOOGLE_API_KEY'));
  assert(workflow.includes('UNSPLASH_ACCESS_KEY'));
  assert(workflow.includes('PEXELS_API_KEY'));
  assert(workflow.includes('actions/workflows/ci.yml/dispatches'));

  assert(worker.includes('GEMINI_MODEL = "gemini-3.1-flash-image"'));
  assert(worker.indexOf('try_gemini') < worker.indexOf('try_unsplash'));
  assert(worker.indexOf('try_unsplash') < worker.indexOf('try_pexels'));
  assert(worker.includes('return local_fallback(repo, post, head_ref, token, attempts)'));
  assert(worker.includes('local://'));
  assert(worker.includes('ARTICLE_IMAGE_COMMITTED'));

  assert(gate.includes('New article requires a trusted local image; no-image publication is forbidden'));
  assert(gate.includes('Image Pipeline Version: 2'));
  assert(gate.includes('generated|stock|local_fallback'));
  assert(gate.includes('Image SHA-256 mismatch'));
  assert(gate.includes('Image dimensions mismatch'));
  assert(!gate.includes('No-image fallback must record'));

  assert(generation.includes('scripts/jules_article_runner_v3.py'));
  assert(runner.includes('Jules owns ARTICLE TEXT ONLY'));
  assert(runner.includes('The new article MUST omit'));
  assert(runner.includes('trusted GitHub Actions stage'));
}

function testIndependentArticlePrGateRuntime() {
  execFileSync('python3', ['-c', `
import runpy, struct, hashlib
m = runpy.run_path('.github/scripts/validate-article-pr.py')
evaluate = m['evaluate']
base = [{'id':'older'}]
content = '<p>' + ('מילה ' * 700) + '</p>' + ('<h3>שאלה</h3>' * 5)
base_pr = {
  'state':'open','draft':False,'title':'Publish Kesher article: valid-new-post',
  'base':{'ref':'main','repo':{'full_name':'test/repo'}},
  'head':{'repo':{'full_name':'test/repo'}},
}
checks = [{'name':'verify','conclusion':'success'}]

no_image = {'id':'valid-new-post','content':content}
errors = evaluate(base_pr, [{'filename':'src/data/posts.json'}], checks, base, base+[no_image], lambda _: b'')
assert any('no-image publication is forbidden' in e for e in errors), errors

png = b'\\x89PNG\\r\\n\\x1a\\n' + b'\\x00'*8 + struct.pack('>II',1200,675) + b'fixture'
sha = hashlib.sha256(png).hexdigest()
body = f'''Image Pipeline Version: 2
Image Provider: Local
Image Attempt Chain: gemini/unsplash/pexels/local-curated
Image Generation Result: local_fallback
Image Source URL: local://public/images/generated/blog/listening-in-relationships.jpg
Image SHA-256: {sha}
Image Dimensions: 1200x675
Image Visual Match: זוג בשיחה פנים אל פנים המדגישה הקשבה ותקשורת באופן ברור'''
pr = dict(base_pr, body=body)
post = dict(no_image, image='/images/generated/blog/valid-new-post.png', imageAlt='זוג בשיחה פנים אל פנים המדגישה הקשבה ותקשורת באופן ברור')
files = [{'filename':'src/data/posts.json'}, {'filename':'public/images/generated/blog/valid-new-post.png'}]
errors = evaluate(pr, files, checks, base, base+[post], lambda _: png)
assert errors == [], errors

bad_body = body.replace(sha, '0'*64)
errors = evaluate(dict(pr, body=bad_body), files, checks, base, base+[post], lambda _: png)
assert any('SHA-256 mismatch' in e for e in errors), errors

video = dict(post, video='/videos/generated/placeholder.mp4')
errors = evaluate(pr, files+[{'filename':'public/videos/generated/placeholder.mp4'}], checks, base, base+[video], lambda _: png)
assert any('video' in e.lower() for e in errors), errors
`]);
}

function testArticleAutomergeAndRepairContracts() {
  const workflow = read('.github/workflows/auto-merge-article-prs.yml');
  const controller = read('.github/scripts/article-pr-controller.py');
  const controllerV3 = read('.github/scripts/article-pr-controller-v3.py');
  const gate = read('.github/scripts/validate-article-pr.py');
  assert(workflow.includes('Checkout trusted article controller'));
  assert(workflow.includes('ref: main'));
  assert(workflow.includes('python3 .github/scripts/article-pr-controller-v3.py'));
  assert(/permissions:[\s\S]*actions:\s*write/.test(workflow));
  assert(controller.includes('load_validator()'));
  assert(controller.includes('validator.evaluate('));
  assert(controllerV3.includes('LEGACY_PATH = Path(__file__).with_name("article-pr-controller.py")'));
  assert(controllerV3.includes('MAX_TOTAL_CONTENT_ATTEMPTS = 3'));
  assert(controllerV3.includes('Repair THE SAME PR #'));
  assert(controller.indexOf('merged = request_json(') < controller.indexOf('/actions/workflows/deploy.yml/dispatches'));
  assert(gate.includes('Expected exactly one new article'));
  assert(gate.includes('Article publication PR may not modify or remove existing posts'));
  assert(gate.includes('New article word count must be 700-1100'));
}

function testJulesWatchdogContracts() {
  const watchdog = read('.github/scripts/watch-jules-session.py');
  for (const contract of [
    'AWAITING_USER_FEEDBACK', 'WAITING_FOR_USER', ':sendMessage', 'max_replacements',
    'AUTONOMOUS RECOVERY REQUIREMENT', 'COMPLETED with changeSet but no pullRequest',
    'AUTONOMOUS_CLEANUP_GRACE_SECONDS', 'REPEATED_WAITING_CONTINUATION',
    'max_waiting_continuations', 'Use Jules built-in PR submission', '"PAUSED"',
    'DELIVERY RECOVERY REQUIREMENT:', 'max_delivery_replacements', 'Previous changeSet candidate paths:',
  ]) {
    assert(watchdog.includes(contract), `Jules watchdog missing ${contract}`);
  }
  assert.strictEqual(watchdog.split('deadline = time.monotonic() + max_seconds').length - 1, 5);
}

function testOtherAuditAutonomyContracts() {
  const audit = read('.github/workflows/auto-merge-jules-audit-prs.yml');
  const seo = read('.github/workflows/jules-daily-seo-geo-review.yml');
  const mobile = read('.github/workflows/jules-daily-mobile-review.yml');
  const site = read('.github/workflows/jules-nightly-site-fixes.yml');
  const industry = read('.github/workflows/jules-daily-industry-benchmarking.yml');
  assert(audit.includes('Closed zero-file stale/duplicate audit PR.'));
  assert(audit.includes('Failing explicitly instead of reporting false success.'));
  assert(audit.includes('cron: "17,47 * * * *"'));
  assert(audit.includes('mobile_route_evidence_valid'));
  assert(seo.includes('Final live-duplicate gate:'));
  assert(seo.includes('Discovery-to-action invariant:'));
  assert(mobile.includes('Asking whether to fix that issue or inspect another page is forbidden.'));
  assert(site.includes('Public-route evidence rule:'));
  assert(industry.includes('Evidence-before-edit gate:'));
  for (const workflow of [seo, mobile, site, industry]) {
    assert(workflow.includes('Enforce autonomous terminal Jules state'));
    assert(workflow.includes('.github/scripts/watch-jules-session.py'));
  }
}

function testTechnicalVideoPublicationCannotBeRegressed() {
  const daily = read('.github/workflows/kesher-daily-video.yml');
  const contract = JSON.parse(read('config/kesher-production-contract.json'));
  assert.strictEqual(contract.video.publication_gate, 'technical');
  assert.strictEqual(contract.video.jules_review, 'advisory');
  assert.strictEqual(contract.video.durable_state_artifacts_to_keep, 3);
  assert.strictEqual(contract.video.max_attempts_per_stage, 3);
  assert(daily.includes('Jules performs strict advisory review'));
  assert(daily.includes('Prepare technically verified upload'));
  assert(daily.includes('Upload exact technically verified MP4'));
  assert(daily.includes('continue-on-error: true'));
  assert(!daily.includes('mandatory Jules'));
  assert(!daily.includes('Jules-approved MP4'));
  assert(!daily.includes('Upload only after all mandatory review gates approve'));
  assert(daily.includes('Keep the newest three durable state artifacts'));
  assert(daily.includes('| .[3:] | .[].id'));
}

testControllerHardening();
testContentValidatorContracts();
testTrustedArticleImageV2();
testIndependentArticlePrGateRuntime();
testArticleAutomergeAndRepairContracts();
testJulesWatchdogContracts();
testOtherAuditAutonomyContracts();
testTechnicalVideoPublicationCannotBeRegressed();
console.log('All automation gates tests passed.');
