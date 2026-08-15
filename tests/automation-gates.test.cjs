const assert = require('assert');
const { execFileSync, execSync } = require('child_process');
const fs = require('fs');


function testControllerHardening() {
    const seoWorkflow = fs.readFileSync('.github/workflows/jules-daily-seo-geo-review.yml', 'utf8');
    const mobileWorkflow = fs.readFileSync('.github/workflows/jules-daily-mobile-review.yml', 'utf8');
    const siteFixWorkflow = fs.readFileSync('.github/workflows/jules-nightly-site-fixes.yml', 'utf8');
    const industryWorkflow = fs.readFileSync('.github/workflows/jules-daily-industry-benchmarking.yml', 'utf8');
    const weeklyWorkflow = fs.readFileSync('.github/workflows/jules-weekly-content-review.yml', 'utf8');
    const articlePolicy = fs.readFileSync('.github/prompts/jules-weekday-article-update.md', 'utf8');

    for (const [name, content] of [
        ['SEO/GEO', seoWorkflow],
        ['mobile', mobileWorkflow],
        ['site-fix', siteFixWorkflow],
        ['industry-benchmarking', industryWorkflow],
        ['weekly-content-review', weeklyWorkflow],
    ]) {
        assert(
            content.includes('strictly defined as a couples counselor'),
            `${name} workflow must strictly define couples counselor`
        );
        assert(
            (content.includes('Do NOT add, change, or refer to divorce (גירושין)') || content.includes('Do NOT optimize for, benchmark against, add, or refer to divorce (גירושין)')) && content.includes('legal services (עריכת דין / עו') && content.includes('ד), or family mediation (גישור)'),
            `${name} workflow must strictly forbid divorce, legal, and mediation`
        );
    }

    assert(
        !articlePolicy.includes('מגשרת מוסמכת'),
        'Article policy must not include mediator credentials'
    );
    assert(
        !articlePolicy.includes('עורכת דין בהכשרתה'),
        'Article policy must not include lawyer credentials'
    );
    assert(
        !articlePolicy.includes('גישור כהליך רצוני'),
        'Article policy must not present mediation as an allowed topic'
    );
    assert(
        articlePolicy.includes('אין להוסיף, לשנות או להתייחס לגירושין, שירותים משפטיים') && articlePolicy.includes('או גישור משפחתי בשום מקום במאמר'),
        'Article policy must strictly forbid divorce, legal, and mediation in new articles'
    );
}

function testGenericH3() {
    const regex = /<h3[^>]*>\s*(סיכום|לסיכום|סיכום וצעדים הבאים|צעדים הבאים)\s*<\/h3>/;
    assert(regex.test("<h3>סיכום</h3>"), "Should reject generic H3");
    assert(regex.test("<h3 class=\"title\">צעדים הבאים</h3>"), "Should reject generic H3 with attributes");
    assert(!regex.test("<p>לסיכום, זה חשוב</p>"), "Should allow ordinary prose");
}

function testImageExtraction() {
    const bodyValid = "Image Source URL: https://example.com/img\nImage SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\nImage Dimensions: 1200x900\nMatch: shows a couple.";
    const match = bodyValid.match(/Image SHA-256:\s*([a-f0-9a-fA-F]{64})/);
    assert(match && match[1] === 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', "Should extract SHA-256");
}

function runPythonWorkflowLogic(prBody, filesJson, imageData, expectedExitCode) {
    fs.writeFileSync('pr.json', JSON.stringify({
        state: "open",
        draft: false,
        base: { ref: "main", repo: { full_name: "test/repo" } },
        head: { repo: { full_name: "test/repo" } },
        body: prBody
    }));
    fs.writeFileSync('files.json', JSON.stringify(filesJson));
    fs.writeFileSync('checks.json', JSON.stringify({
        check_runs: [{ name: "verify", conclusion: "success" }]
    }));

    // Create dummy image file to bypass network fetch in test environment by mocking the urllib call
    const pythonScript = `
import json, sys, re, hashlib
pr = json.load(open("pr.json"))
files_data = json.load(open("files.json"))
files = [f["filename"] for f in files_data]
checks = json.load(open("checks.json")).get("check_runs", [])
allowed_files = {"src/data/posts.json", "src/data/postSummaries.json", "public/sitemap.xml", "public/llms.txt", "public/llms-full.txt"}
allowed = all(f in allowed_files or f.startswith("public/images/generated/blog/") for f in files)
ci_passed = any(c.get("name") == "verify" and c.get("conclusion") == "success" for c in checks)

image_file = next((f for f in files_data if f["filename"].startswith("public/images/generated/blog/")), None)
if image_file:
    match = re.search(r"Image SHA-256:\\s*([a-f0-9]{64})", pr.get("body") or "")
    if not match:
        print("Missing or invalid Image SHA-256 in PR body")
        sys.exit(1)
    expected_sha = match.group(1).lower()
    img_data = b"${imageData}"
    actual_sha = hashlib.sha256(img_data).hexdigest()
    if expected_sha != actual_sha:
        print(f"Hash mismatch! Expected {expected_sha}, got {actual_sha}")
        sys.exit(1)

eligible = (
    pr.get("state") == "open"
    and not pr.get("draft")
    and pr["base"]["ref"] == "main"
    and pr["head"]["repo"]["full_name"] == pr["base"]["repo"]["full_name"]
    and "src/data/posts.json" in files
    and allowed
    and ci_passed
)
sys.exit(0 if eligible else 1)
`;
    fs.writeFileSync('test_gate.py', pythonScript);
    try {
        execSync('python3 test_gate.py');
        assert.strictEqual(0, expectedExitCode);
    } catch (e) {
        assert.strictEqual(1, expectedExitCode, "Expected failure but script succeeded or crashed with wrong error");
    } finally {
        fs.unlinkSync('pr.json');
        fs.unlinkSync('files.json');
        fs.unlinkSync('checks.json');
        fs.unlinkSync('test_gate.py');
    }
}

function testWorkflowGate() {
    // 1. Correct structured URL plus actual image hash passes
    const correctHash = require('crypto').createHash('sha256').update("realimage").digest('hex');
    runPythonWorkflowLogic(
        `Image Source URL: https://example.com/img\nImage SHA-256: ${correctHash}`,
        [{ filename: "src/data/posts.json" }, { filename: "public/images/generated/blog/img.jpg", raw_url: "fake" }],
        "realimage",
        0
    );

    // 2. Unrelated URL/hash fails validation
    runPythonWorkflowLogic(
        `Image Source URL: https://example.com/img\nImage SHA-256: 1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef`,
        [{ filename: "src/data/posts.json" }, { filename: "public/images/generated/blog/img.jpg", raw_url: "fake" }],
        "realimage",
        1
    );

    // 3. Wrong hash fails
    runPythonWorkflowLogic(
        `Image Source URL: https://example.com/img\nImage SHA-256: ${require('crypto').createHash('sha256').update("wrongimage").digest('hex')}`,
        [{ filename: "src/data/posts.json" }, { filename: "public/images/generated/blog/img.jpg", raw_url: "fake" }],
        "realimage",
        1
    );

    // 4. Missing hash lines in body when image is present fails
    runPythonWorkflowLogic(
        `Just a normal PR body without hash`,
        [{ filename: "src/data/posts.json" }, { filename: "public/images/generated/blog/img.jpg", raw_url: "fake" }],
        "realimage",
        1
    );

    // 5. No-image fallback passes
    runPythonWorkflowLogic(
        `No image for this post`,
        [{ filename: "src/data/posts.json" }],
        "",
        0
    );
}

function testContentValidatorContracts() {
    const validator = fs.readFileSync('scripts/validate-content.cjs', 'utf8');
    assert(
        validator.includes("published.map((post) => post.image).filter(Boolean)"),
        "No-image fallback must not fail uniqueness validation"
    );
    assert(
        validator.includes("if (post.image) {"),
        "Local image checks must run only when an image exists"
    );
    assert(
        validator.includes('const visibleProse = `${post.title}\\n${post.excerpt}\\n${stripHtml(post.content)}`'),
        "Formulaic phrase validation must cover title, excerpt, and content"
    );
    for (const phrase of [
                "זה קורה כמעט לכל מי",
        "טבעית לחלוטין",
        "הצעד הראשון להתמודדות",
        "המלכודת הגדולה ביותר",
        "הקצב שלכם הוא הקצב שלכם",
        "אין לוח זמנים אוניברסלי",
        "מלאים ושלמים יותר",
"זירת התגוששות",
        "שדה מוקשים",
        "לנווט את התקופה",
        "משפט תגובה קצר וחותך",
        "הבנה עמוקה",
        "חיבור אמיתי",
        "לנווט את החיים",
        "מזמינה אתכם לעשות סדר במחשבות",
        "נובעות לרוב משילוב",
        "הדור הקודם גדל על מסלול חיים מאוד ברור",
        "החריגה ממנו מעוררת אצלם חרדה",
        "התגובה הטבעית היא",
        "הכלל החשוב ביותר",
    ]) {
        assert(validator.includes(`"${phrase}"`), `Missing observed phrase guard: ${phrase}`);
    }
    assert(
        validator.includes('if (i === 0)'),
        'Newly observed phrase guards must target the latest article without retroactively blocking old content'
    );
    assert(
        validator.includes('Post summaries are stale or incomplete; run npm run generate after the final posts.json edit.'),
        'Content validation must reject a missing or stale generated post summary'
    );
}

function testIndependentArticlePrGate() {
    const workflow = fs.readFileSync('.github/workflows/auto-merge-article-prs.yml', 'utf8');
    const controller = fs.readFileSync('.github/scripts/article-pr-controller.py', 'utf8');
    const gate = fs.readFileSync('.github/scripts/validate-article-pr.py', 'utf8');
    assert(
        workflow.includes('python3 .github/scripts/article-pr-controller.py') &&
        controller.includes('load_validator()') &&
        controller.includes('validator.evaluate('),
        'Article auto-merge must execute the independent trusted quality gate through the self-healing controller'
    );
    for (const contract of [
        'New article word count must be 700-1100',
        'Article PRs may not contain video files',
        'New article may not contain a video field',
        'Committed image requires Image Generation Result success|generated',
        'Image Visual Match',
        'Image dimensions mismatch',
        'Expected exactly one new article',
        'Article publication PR may not modify or remove existing posts',
    ]) {
        assert(gate.includes(contract), `Independent article gate is missing contract: ${contract}`);
    }

    execFileSync('python3', ['-c', `
import runpy
gate = runpy.run_path('.github/scripts/validate-article-pr.py')
evaluate = gate['evaluate']
base = [{'id': 'older'}]
pr = {
    'state': 'open', 'draft': False, 'title': 'Publish Kesher article: valid-new-post',
    'body': '''Image Generation Attempt: DeepAI/Gemini/Fallback pool
Image Generation Result: blocked
Image Fallback Attempt: Unsplash/Pexels
Image Fallback Result: no_pixel_verified_match
Image Source URL: none''',
    'base': {'ref': 'main', 'repo': {'full_name': 'test/repo'}},
    'head': {'repo': {'full_name': 'test/repo'}},
}
checks = [{'name': 'verify', 'conclusion': 'success'}]
files = [{'filename': 'src/data/posts.json'}]
valid = {'id': 'valid-new-post', 'content': '<p>' + ('מילה ' * 700) + '</p>' + ('<h3>שאלה</h3>' * 5)}
assert evaluate(pr, files, checks, base, base + [valid], lambda _: b'') == []

thin = dict(valid, content='<p>' + ('מילה ' * 603) + '</p>' + ('<h3>שאלה</h3>' * 5))
errors = evaluate(pr, files, checks, base, base + [thin], lambda _: b'')
assert any('found 608' in error for error in errors), errors

video = dict(valid, video='/videos/generated/placeholder.mp4')
video_files = files + [{'filename': 'public/videos/generated/placeholder.mp4'}]
errors = evaluate(pr, video_files, checks, base, base + [video], lambda _: b'')
assert any('video' in error.lower() for error in errors), errors

image_pr = dict(pr, body='''Image Generation Attempt: DeepAI
Image Generation Result: blocked
Image Source URL: https://api.deepai.org/example.jpg
Image SHA-256: 0000000000000000000000000000000000000000000000000000000000000000
Image Dimensions: 1x1
Image Visual Match: Friday dinner family scene is visible.''')
image_post = dict(valid, image='/images/generated/blog/valid-new-post.jpg', imageAlt='תיאור')
image_files = files + [{'filename': 'public/images/generated/blog/valid-new-post.jpg'}]
errors = evaluate(image_pr, image_files, checks, base, base + [image_post], lambda _: b'not-an-image')
assert any('requires Image Generation Result success|generated' in error for error in errors), errors
`]);
}

function testAutomergeDeployContracts() {
    const auditWorkflow = fs.readFileSync('.github/workflows/auto-merge-jules-audit-prs.yml', 'utf8');
    const articleWorkflow = fs.readFileSync('.github/workflows/auto-merge-article-prs.yml', 'utf8');
    const articleController = fs.readFileSync('.github/scripts/article-pr-controller.py', 'utf8');
    for (const [name, workflow, deploySource] of [
        ['audit', auditWorkflow, auditWorkflow],
        ['article', articleWorkflow, articleController],
    ]) {
        assert(
            deploySource.includes('/actions/workflows/deploy.yml/dispatches'),
            `${name} auto-merge must dispatch deployment after a successful merge`
        );
        assert(
            /permissions:[\s\S]*actions:\s*write/.test(workflow),
            `${name} auto-merge must have actions: write for deploy dispatch`
        );
    }
    assert(
        auditWorkflow.lastIndexOf('dispatch_deploy()') > auditWorkflow.indexOf('Merged successfully.'),
        'Audit deploy dispatch must occur only after a successful merge'
    );
    assert(
        articleController.indexOf('merged = request_json(') < articleController.indexOf('/actions/workflows/deploy.yml/dispatches'),
        'Article deploy dispatch must occur only after checking the merge response'
    );
    const articleGate = fs.readFileSync('.github/scripts/validate-article-pr.py', 'utf8');
    assert(
        articleGate.includes('"src/data/postSummaries.json"'),
        'Article auto-merge must accept the generated post summary index'
    );
    assert(
        articleWorkflow.includes('Checkout trusted article controller') && articleWorkflow.includes('ref: main'),
        'Article auto-merge must checkout trusted main before running its controller and validator'
    );
    assert(
        auditWorkflow.includes('Closed zero-file stale/duplicate audit PR.'),
        'Audit auto-merge must close zero-file stale duplicate PRs'
    );
    assert(
        auditWorkflow.includes('Failing explicitly instead of reporting false success.'),
        'Audit auto-merge must not return green after a rejected merge'
    );
    assert(
        auditWorkflow.includes('cron: "17,47 * * * *"'),
        'Audit auto-merge must rescan after token-dispatched CI completion'
    );

    const seoWorkflow = fs.readFileSync('.github/workflows/jules-daily-seo-geo-review.yml', 'utf8');
    const mobileWorkflow = fs.readFileSync('.github/workflows/jules-daily-mobile-review.yml', 'utf8');
    const siteFixWorkflow = fs.readFileSync('.github/workflows/jules-nightly-site-fixes.yml', 'utf8');
    const industryWorkflow = fs.readFileSync('.github/workflows/jules-daily-industry-benchmarking.yml', 'utf8');
    const watchdog = fs.readFileSync('.github/scripts/watch-jules-session.py', 'utf8');
    assert(
        seoWorkflow.includes('Final live-duplicate gate:'),
        'SEO/GEO prompt must recheck current main and forbid zero-file duplicate PRs'
    );
    for (const [name, workflow] of [
        ['SEO/GEO', seoWorkflow],
        ['mobile', mobileWorkflow],
        ['site-fix', siteFixWorkflow],
        ['industry-benchmarking', industryWorkflow],
    ]) {
        assert(
            workflow.includes('Enforce autonomous terminal Jules state'),
            `${name} workflow must verify Jules completion instead of only session creation`
        );
        assert(
            workflow.includes('.github/scripts/watch-jules-session.py'),
            `${name} workflow must run the shared Jules terminal-state watchdog`
        );
        assert(
            workflow.indexOf('actions/checkout@') < workflow.indexOf('.github/scripts/watch-jules-session.py'),
            `${name} workflow must checkout before running the repository-owned watchdog`
        );
    }
    for (const contract of [
        'AWAITING_USER_FEEDBACK',
        'WAITING_FOR_USER',
        ':sendMessage',
        'max_replacements',
        'AUTONOMOUS RECOVERY REQUIREMENT',
        'COMPLETED with changeSet but no pullRequest',
        'AUTONOMOUS_CLEANUP_GRACE_SECONDS',
        'REPEATED_WAITING_CONTINUATION',
        'max_waiting_continuations',
        'Use Jules built-in PR submission',
        '"PAUSED"',
        'DELIVERY RECOVERY REQUIREMENT:',
        'max_delivery_replacements',
        'Previous changeSet candidate paths:',
    ]) {
        assert(
            watchdog.includes(contract),
            `Jules watchdog is missing terminal-state contract: ${contract}`
        );
    }
    assert.strictEqual(
        watchdog.split('deadline = time.monotonic() + max_seconds').length - 1,
        5,
        'Each bounded replacement must receive a fresh full session budget'
    );
    execFileSync('python3', ['-c', `
import runpy
watchdog = runpy.run_path(".github/scripts/watch-jules-session.py")
validate = watchdog["terminal_output_contract"]
assert validate({"outputs": []})[0]
assert validate({"outputs": [{"pullRequest": {"url": "https://example.test/pr/1"}}]})[0]
assert not validate({"outputs": [{"changeSet": {"gitPatch": {}}}]})[0]
assert validate({"outputs": [{"changeSet": {}}, {"pullRequest": {"url": "https://example.test/pr/1"}}]})[0]
paths = watchdog["change_set_paths"]({"outputs": [
    {"changeSet": {"gitPatch": {"unidiffPatch": "diff --git a/src/a.ts b/src/a.ts\\n"}}},
    {"changeSet": {"gitPatch": {"unidiffPatch": "diff --git a/src/a.ts b/src/a.ts\\ndiff --git a/src/b.ts b/src/b.ts\\n"}}},
]})
assert paths == ["src/a.ts", "src/b.ts"]
`]);
    assert(
        seoWorkflow.includes('Discovery-to-action invariant:'),
        'SEO/GEO prompt must convert discovery into autonomous action instead of a question'
    );
    assert(
        mobileWorkflow.includes('Asking whether to fix that issue or inspect another page is forbidden.'),
        'Mobile prompt must proceed autonomously after reproducing an issue'
    );
    assert(
        mobileWorkflow.includes('Known-regression priority:') &&
        mobileWorkflow.includes('`.heroWhatsapp` and `.quickDock`'),
        'Mobile prompt must prioritize the known fixed-dock/hero CTA collision'
    );
    assert(
        mobileWorkflow.includes('Public-route gate:') &&
        mobileWorkflow.includes('`/beta`, `/beta2`, route experiments, route-specific 404s') &&
        mobileWorkflow.includes('Route HTTP status: 200') &&
        mobileWorkflow.includes('--max-seconds 7200'),
        'Mobile prompt must reject unpublished routes and allow enough time for autonomous completion'
    );
    assert(
        siteFixWorkflow.includes('Public-route evidence rule:') &&
        siteFixWorkflow.includes('a component filename such as `BetaPage`') &&
        siteFixWorkflow.includes('--max-seconds 7200'),
        'Site-fix prompt must reject dead route evidence and allow enough time for autonomous completion'
    );
    assert(
        seoWorkflow.includes('--max-seconds 7200'),
        'SEO/GEO watchdog must allow enough time for a terminal PR or clean no-op'
    );
    assert(
        auditWorkflow.includes('mobile_route_evidence_valid') &&
        auditWorkflow.includes('exact route, HTTP 200, canonical, heading') &&
        auditWorkflow.includes('{"/beta", "/beta2"}'),
        'Audit auto-merge must independently reject dead/experimental mobile route evidence'
    );
    assert(
        auditWorkflow.includes('is an industry review and requires manual review') &&
        !auditWorkflow.includes('content review|mobile review|SEO GEO review|industry review|site fixes'),
        'Industry benchmarking PRs must never enter the audit auto-merge eligibility regex'
    );
    assert(
        articleController.includes('def is_article_scope(') &&
        articleController.includes('path == "src/data/posts.json"') &&
        articleController.includes('path.startswith(IMAGE_PREFIX)') &&
        articleController.includes('send_jules_repair(') &&
        articleController.includes('Repair THE SAME PR AND THE SAME BRANCH') &&
        articleController.includes('MAX_REPAIRS = 2'),
        'Rejected article PRs must enter bounded same-PR Jules self-repair without affecting unrelated PRs'
    );
    assert(
        auditWorkflow.includes('                  evidence_prefix = r"^\\s*(?:[-*]\\s*)?"'),
        'Audit auto-merge must accept exact route evidence with or without a Markdown bullet'
    );
    assert(
        siteFixWorkflow.includes('Offering those paths to the user is forbidden.'),
        'Site-fix prompt must complete the selected terminal path without asking'
    );
    assert(
        siteFixWorkflow.includes('a Vite or build-tool recommendation is not by itself a verified defect'),
        'Site-fix prompt must reject warning-only dependency migrations'
    );
    assert(
        siteFixWorkflow.includes('`AIChatbot` returns `null` at viewports up to 768px') &&
        siteFixWorkflow.includes('a hidden consent launcher as a mobile defect'),
        'Site-fix prompt must reject dead-code mobile AI-chat positioning changes'
    );
    assert(
        industryWorkflow.includes('exact public competitor page URLs actually inspected') &&
        industryWorkflow.includes('never report COMPLETED with a changeSet but no pull request'),
        'Industry benchmarking must require source evidence and a verified terminal PR/no-op'
    );
    assert(
        industryWorkflow.includes('Evidence-before-edit gate:') &&
        industryWorkflow.includes('Clinical boundaries, treatment contraindications') &&
        industryWorkflow.includes('Do not create scratch search scripts in the repository.'),
        'Industry benchmarking must gather evidence before edits and reject unsupported clinical changes'
    );
    assert(
        industryWorkflow.includes('title_pattern = re.compile') &&
        industryWorkflow.includes('branch_pattern = re.compile') &&
        !industryWorkflow.includes('(pr.get("body") or "")'),
        'Industry backlog gate must use task identity, not generic service terms in arbitrary PR bodies'
    );
    assert(
        seoWorkflow.includes('must not bulk-rewrite article bodies'),
        'SEO/GEO prompt must not turn a technical review into bulk article publication work'
    );

    const articlePolicy = fs.readFileSync('.github/prompts/jules-weekday-article-update.md', 'utf8');
    const articleRuntimeWorkflow = fs.readFileSync('.github/workflows/jules-weekday-article.yml', 'utf8');
    assert(
        !articleRuntimeWorkflow.includes('\n- Every new article MUST have both') &&
        articleRuntimeWorkflow.includes('stale_media_block = "\\n".join(['),
        'Article runtime prompt replacement must stay indented inside the YAML run block'
    );
    assert(
        articlePolicy.includes('appears exactly once in `src/data/posts.json`, `src/data/postSummaries.json`'),
        'Article policy must require generated-index consistency for the new article id'
    );
    assert(
        articlePolicy.includes('schema image property must be omitted entirely, and rendering components must conditionally render image elements rather than passing an empty string to getImageDimensions'),
        'Article policy must enforce truthful no-image fallback rendering'
    );
    for (const observedArticleFailure of [
        'זה קורה כמעט לכל מי',
        'טבעית לחלוטין',
        'הצעד הראשון להתמודדות',
        'המלכודת הגדולה ביותר',
        'הקצב שלכם הוא הקצב שלכם',
        'אין לוח זמנים אוניברסלי',
        'מלאים ושלמים יותר',
    ]) {
        assert(
            articlePolicy.includes(observedArticleFailure),
            `Article prompt must forbid observed formulaic output: ${observedArticleFailure}`
        );
    }
    assert(
        articlePolicy.includes('הכותרת, הפתיח וגוף המאמר חייבים לשמור על אותה אסטרטגיית פנייה'),
        'Article prompt must require consistent inclusive address across title and body'
    );
    for (const requiredEvidence of [
        'Image Generation Attempt: DeepAI',
        'Image Generation Result: unavailable|blocked|api_error|rejected_visual_quality',
        'Image Fallback Attempt: Unsplash/Pexels',
        'Image Fallback Result: no_pixel_verified_match|unavailable|blocked',
        'Image Source URL: none',
    ]) {
        assert(
            articlePolicy.includes(requiredEvidence),
            `Article policy must require structured no-image evidence: ${requiredEvidence}`
        );
    }
    assert(
        articlePolicy.includes('700-1,100 whitespace-delimited words') &&
        articlePolicy.includes('Article publication runs do not create videos') &&
        articlePolicy.includes('Image Generation Result: success|generated'),
        'Article policy must reject short articles, placeholder video, and contradictory image success evidence'
    );
    assert(
        articlePolicy.includes('describe actual visible pixels') &&
        articlePolicy.includes('visibly contain both an adult and a child in a supportive interaction') &&
        articlePolicy.includes('Abstract symbolism such as hands forming a heart') &&
        articlePolicy.includes('record the structured truthful no-image fallback'),
        'Article policy must explicitly require strict pixel-level semantic image verification and reject abstract symbolism'
    );
}

testControllerHardening();
testGenericH3();
testImageExtraction();
testWorkflowGate();
testContentValidatorContracts();
testIndependentArticlePrGate();
testAutomergeDeployContracts();
console.log('All automation gates tests passed.');
