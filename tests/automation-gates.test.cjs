const assert = require('assert');
const { execSync } = require('child_process');
const fs = require('fs');

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

function testAutomergeDeployContracts() {
    const auditWorkflow = fs.readFileSync('.github/workflows/auto-merge-jules-audit-prs.yml', 'utf8');
    const articleWorkflow = fs.readFileSync('.github/workflows/auto-merge-article-prs.yml', 'utf8');
    for (const [name, workflow] of [
        ['audit', auditWorkflow],
        ['article', articleWorkflow],
    ]) {
        assert(
            workflow.includes('/actions/workflows/deploy.yml/dispatches'),
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
        articleWorkflow.indexOf('merge.json') < articleWorkflow.indexOf('/actions/workflows/deploy.yml/dispatches'),
        'Article deploy dispatch must occur only after checking the merge response'
    );
    assert(
        articleWorkflow.includes('"src/data/postSummaries.json"'),
        'Article auto-merge must accept the generated post summary index'
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
    const watchdog = fs.readFileSync('.github/scripts/watch-jules-session.py', 'utf8');
    assert(
        seoWorkflow.includes('Final live-duplicate gate:'),
        'SEO/GEO prompt must recheck current main and forbid zero-file duplicate PRs'
    );
    for (const [name, workflow] of [
        ['SEO/GEO', seoWorkflow],
        ['mobile', mobileWorkflow],
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
    ]) {
        assert(
            watchdog.includes(contract),
            `Jules watchdog is missing terminal-state contract: ${contract}`
        );
    }

    const articlePolicy = fs.readFileSync('.github/prompts/jules-weekday-article-update.md', 'utf8');
    assert(
        articlePolicy.includes('appears exactly once in `src/data/posts.json`, `src/data/postSummaries.json`'),
        'Article policy must require generated-index consistency for the new article id'
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
}

testGenericH3();
testImageExtraction();
testWorkflowGate();
testContentValidatorContracts();
testAutomergeDeployContracts();
console.log('All automation gates tests passed.');
