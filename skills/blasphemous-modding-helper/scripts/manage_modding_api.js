#!/usr/bin/env node
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const lockState = require('./modding_api_lock');
const runtime = require('./modding_api_runtime');

const SCRIPT_DIR = __dirname;
const OFFICIAL_REPOSITORY = 'https://github.com/BrandenEK/Blasphemous.ModdingAPI.git';
const state = {
    operation: '',
    scope: '',
    targetPath: '',
    preferencesFile: '',
    selector: '',
    metadataFile: '',
    dryRun: false,
    offline: false,
    selectorExplicit: false,
    targetExplicit: false,
    preferencesExplicit: false,
    testMode: false,
    testRepository: '',
    testHome: '',
    testNetworkFailure: false,
    networkState: 'unknown',
    currentHead: '<unavailable>',
    worktreeState: 'unknown',
    lockFile: '<unavailable>',
    selectorKind: '',
    resolvedRef: '',
    resolvedTag: '',
    resolvedCommit: '',
    repository: OFFICIAL_REPOSITORY,
    resolverError: ''
};

class Stop extends Error {
    constructor(code) {
        super('managed exit');
        this.code = code;
    }
}

function text(value) {
    return value === undefined || value === null ? '' : String(value);
}

function boolText(value) {
    return value ? 'true' : 'false';
}

function usage() {
    process.stdout.write(
        'Usage:\n' +
        '  manage_modding_api --operation check|update [options]\n\n' +
        'Options:\n' +
        '  --operation check|update  Explicitly validate or refresh the local checkout.\n' +
        '  --scope project|user      Use the approved project or user reference path.\n' +
        '  --target-path PATH        Override the reference checkout path.\n' +
        '  --preferences-file PATH   Read the selector and path from preferences.md.\n' +
        '  --selector SELECTOR       latest, tag:REF, branch:REF, or commit:SHA.\n' +
        '  --metadata-file PATH      Test-only resolver metadata fixture.\n' +
        '  --offline                 Validate only from the sibling lock state.\n' +
        '  --dry-run                 Plan without fetching, checking out, or writing lock state.\n' +
        '  --help                    Show this help.\n\n' +
        'The lock state is stored beside the checkout as <target-path>.lock. Update and\n' +
        'check never reset, stash, delete, or replace an existing checkout.\n'
    );
}

function parseArgs(argv) {
    for (let index = 0; index < argv.length; index += 1) {
        const raw = argv[index];
        const key = raw.toLowerCase();
        const value = () => {
            if (index + 1 >= argv.length) {
                fail(2, raw + ' requires a value', 'Use --help to see the supported options.');
            }
            index += 1;
            return argv[index];
        };
        switch (key) {
            case '--operation':
            case '-operation':
                state.operation = value();
                break;
            case '--scope':
            case '-scope':
                state.scope = value();
                break;
            case '--target-path':
            case '-targetpath':
                state.targetPath = value();
                state.targetExplicit = true;
                break;
            case '--preferences-file':
            case '-preferencesfile':
                state.preferencesFile = value();
                state.preferencesExplicit = true;
                break;
            case '--selector':
            case '-selector':
                state.selector = value();
                state.selectorExplicit = true;
                break;
            case '--metadata-file':
            case '-metadatafile':
                state.metadataFile = value();
                break;
            case '--offline':
            case '-offline':
                state.offline = true;
                break;
            case '--dry-run':
            case '-dryrun':
                state.dryRun = true;
                break;
            case '--test-mode':
                state.testMode = true;
                break;
            case '--test-repository':
                state.testRepository = value();
                break;
            case '--test-home':
                state.testHome = value();
                break;
            case '--test-network-failure':
                state.testNetworkFailure = true;
                break;
            case '--help':
            case '-help':
            case '-h':
                usage();
                process.exitCode = 0;
                return false;
            default:
                fail(2, 'unknown option: ' + raw, 'Use --help to see the supported options.');
        }
    }
    return true;
}

function escapeRegExp(value) {
    return value.replace(/[|\\{}()[\]^$+*?.-]/g, '\\$&');
}

function readKeyValue(file, key) {
    if (!file || !fs.existsSync(file)) {
        return '';
    }
    const content = fs.readFileSync(file, 'utf8');
    const pattern = new RegExp('^[ \\t]*' + escapeRegExp(key) + '[ \\t]*:[ \\t]*(.*)$');
    for (const line of content.split(/\r?\n/)) {
        const match = line.match(pattern);
        if (match) {
            return match[1].trim();
        }
    }
    return '';
}

function hasKey(file, key) {
    if (!file || !fs.existsSync(file)) {
        return false;
    }
    const content = fs.readFileSync(file, 'utf8');
    const pattern = new RegExp('^[ \\t]*' + escapeRegExp(key) + '[ \\t]*:');
    return content.split(/\r?\n/).some(line => pattern.test(line));
}

function canonicalRepository(value) {
    let result = text(value).trim().replace(/\/+$/, '');
    const wslPath = result.match(/^\/(?:mnt\/)?([A-Za-z])\/(.*)$/);
    if (wslPath) {
        result = wslPath[1].toUpperCase() + ':/' + wslPath[2];
    }
    result = result.replace(/\\/g, '/');
    const sshRepository = result.match(/^git@([^:]+):(.+)$/i);
    if (sshRepository) {
        result = 'https://' + sshRepository[1] + '/' + sshRepository[2];
    }
    const sshUrl = result.match(/^ssh:\/\/git@([^/]+)\/(.+)$/i);
    if (sshUrl) {
        result = 'https://' + sshUrl[1] + '/' + sshUrl[2];
    }
    result = result.replace(/^https?:\/\/(?:www\.)?github\.com\//i, 'https://github.com/');
    if (result.toLowerCase().endsWith('.git')) {
        result = result.slice(0, -4);
    }
    return result.toLowerCase();
}

function validCheckedAt(value) {
    return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(text(value)) && !Number.isNaN(Date.parse(value));
}

function currentHead() {
    if (!state.targetPath || !fs.existsSync(state.targetPath)) {
        return '<unavailable>';
    }
    const result = runtime.runGit(state.targetPath, ['rev-parse', 'HEAD']);
    return result.code === 0 ? result.output.trim().split(/\r?\n/)[0] : '<unavailable>';
}

function worktreeState() {
    if (!state.targetPath || !fs.existsSync(state.targetPath)) {
        return 'missing';
    }
    const inside = runtime.runGit(state.targetPath, ['rev-parse', '--is-inside-work-tree']);
    if (inside.code !== 0 || inside.output.trim() !== 'true') {
        return 'invalid';
    }
    const status = runtime.runGit(state.targetPath, ['status', '--porcelain', '--untracked-files=all']);
    if (status.code !== 0) {
        return 'invalid';
    }
    return status.output.trim().length > 0 ? 'dirty' : 'clean';
}

function printErrorReport(code, cause, nextStep) {
    process.stderr.write(
        '[ERROR REPORT]\n' +
        'operation: ' + (state.operation || '<unset>') + '\n' +
        'target_path: ' + (state.targetPath || '<unset>') + '\n' +
        'selector: ' + (state.selector || '<unset>') + '\n' +
        'current_head: ' + currentHead() + '\n' +
        'worktree_state: ' + worktreeState() + '\n' +
        'network_state: ' + (state.networkState || 'unknown') + '\n' +
        'cause: ' + cause + '\n' +
        'next_step: ' + nextStep + '\n'
    );
    return code;
}

function fail(code, cause, nextStep) {
    throw new Stop(printErrorReport(code, cause, nextStep));
}

function isTestMode() {
    return state.testMode || process.env.MODDING_API_TEST_MODE === '1';
}

function validateNodeRuntime() {
    const major = Number(process.versions.node.split('.')[0]);
    if (!Number.isInteger(major) || major < 18) {
        fail(1, 'Node.js 18 or newer is required to manage a local reference', 'Install Node.js 18 or newer and retry.');
    }
}

function testRepository() {
    return state.testRepository || process.env.MODDING_API_TEST_REPOSITORY || '';
}

function testHome() {
    return state.testHome || process.env.MODDING_API_TEST_HOME || '';
}

function validateTestOverrides() {
    if ((state.metadataFile || testRepository()) && !isTestMode()) {
        fail(2, 'test-only resolver or repository override requires test mode', 'Use the official resolver without fixtures, or run repository-owned tests with MODDING_API_TEST_MODE=1.');
    }
}

function selectDefaultPaths() {
    const cwd = process.cwd();
    const home = isTestMode() && testHome()
        ? testHome()
        : os.homedir();
    const projectTarget = path.join(cwd, '.skills', 'blasphemous-modding-helper', 'references', 'modding-api');
    const projectPreferences = path.join(cwd, '.skills', 'blasphemous-modding-helper', 'preferences.md');
    const userTarget = path.join(home, '.skills', 'blasphemous-modding-helper', 'references', 'modding-api');
    const userPreferences = path.join(home, '.skills', 'blasphemous-modding-helper', 'preferences.md');

    let defaultTarget = '';
    let defaultPreferences = '';
    if (state.scope) {
        if (state.scope === 'project') {
            defaultTarget = projectTarget;
            defaultPreferences = projectPreferences;
        }
        else {
            defaultTarget = userTarget;
            defaultPreferences = userPreferences;
        }
        if (!state.preferencesFile) {
            state.preferencesFile = defaultPreferences;
        }
    }
    else if (!state.preferencesFile && !state.targetExplicit) {
        if (fs.existsSync(projectPreferences)) {
            defaultTarget = projectTarget;
            defaultPreferences = projectPreferences;
            state.preferencesFile = projectPreferences;
        }
        else if (fs.existsSync(userPreferences)) {
            defaultTarget = userTarget;
            defaultPreferences = userPreferences;
            state.preferencesFile = userPreferences;
        }
    }
    if (state.preferencesFile) {
        state.preferencesFile = lockState.normalizePath(state.preferencesFile);
        if (state.scope && state.preferencesExplicit && state.preferencesFile !== lockState.normalizePath(defaultPreferences)) {
            fail(2, 'preferences file scope does not match --scope ' + state.scope, 'Use the preferences path belonging to the selected scope.');
        }
    }
    return { defaultTarget, defaultPreferences };
}

function readPreferencePath(defaultTarget) {
    if (!state.targetExplicit && state.preferencesFile) {
        const configuredTarget = readKeyValue(state.preferencesFile, 'modding_api_reference_path');
        if (configuredTarget) {
            state.targetPath = configuredTarget;
        }
    }
    if (!state.targetPath) {
        if (defaultTarget) {
            state.targetPath = defaultTarget;
        }
        else {
            fail(2, 'no local reference path was provided', 'Use --target-path, --scope, or configure modding_api_reference_path in preferences.md.');
        }
    }
    state.targetPath = lockState.normalizePath(state.targetPath);
    state.lockFile = state.targetPath + '.lock';
}

function readSelector() {
    if (state.selectorExplicit) {
        return;
    }
    const configuredSelector = readKeyValue(state.preferencesFile, 'modding_api_reference_selector');
    if (configuredSelector) {
        state.selector = configuredSelector;
    }
    else {
        state.selector = 'latest';
    }
    if (!state.selector) {
        fail(2, 'no selector was configured', 'Use --selector or add modding_api_reference_selector to preferences.md.');
    }
}

function validateSelectorSyntax() {
    if (state.selector === 'latest') {
        state.selectorKind = 'release';
        state.resolvedRef = '';
        return;
    }
    let match = state.selector.match(/^tag:(.+)$/);
    if (match) {
        state.selectorKind = 'tag';
        state.resolvedRef = match[1];
        return;
    }
    match = state.selector.match(/^branch:(.+)$/);
    if (match) {
        state.selectorKind = 'branch';
        state.resolvedRef = match[1];
        return;
    }
    match = state.selector.match(/^commit:(.+)$/);
    if (match) {
        state.resolvedRef = match[1];
        if (!/^[0-9a-fA-F]{40}$/.test(state.resolvedRef)) {
            fail(2, 'commit selector must contain a 40-character SHA', 'Use commit:SHA with an exact 40-character commit.');
        }
        state.selectorKind = 'commit';
        return;
    }
    fail(2, 'invalid selector: ' + state.selector, 'Use latest, tag:REF, branch:REF, or commit:SHA.');
}

function loadCheckoutState() {
    if (!fs.existsSync(state.targetPath) || !fs.statSync(state.targetPath).isDirectory()) {
        state.worktreeState = 'missing';
        fail(2, 'reference path does not exist: ' + state.targetPath, 'Run the fresh clone command or provide the configured checkout path.');
    }
    const inside = runtime.runGit(state.targetPath, ['rev-parse', '--is-inside-work-tree']);
    if (inside.code !== 0 || inside.output.trim() !== 'true') {
        state.worktreeState = 'invalid';
        fail(1, 'reference path is not a Git worktree: ' + state.targetPath, 'Use a valid ModdingAPI checkout or clone a fresh reference into a missing path.');
    }
    state.currentHead = currentHead();
    if (state.currentHead === '<unavailable>') {
        fail(1, 'reference worktree has no readable HEAD', 'Repair the checkout manually or create a fresh reference in another path.');
    }
    const status = runtime.runGit(state.targetPath, ['status', '--porcelain', '--untracked-files=all']);
    if (status.code !== 0) {
        fail(1, 'could not inspect reference worktree state', 'Inspect the checkout manually and retry.');
    }
    if (status.output.trim().length > 0) {
        state.worktreeState = 'dirty';
        fail(1, 'reference worktree contains local changes', 'Commit or remove changes manually, then retry; the manager will not stash, reset, or delete them.');
    }
    state.worktreeState = 'clean';

    const origin = runtime.runGit(state.targetPath, ['config', '--get', 'remote.origin.url']);
    if (origin.code !== 0 || !origin.output.trim()) {
        fail(1, 'reference checkout has no origin remote', 'Add the official ModdingAPI origin manually or create a fresh reference.');
    }
    if (canonicalRepository(origin.output.trim()) !== canonicalRepository(state.repository)) {
        fail(1, 'reference origin does not match the official ModdingAPI repository: ' + origin.output.trim(), 'Do not use this checkout; configure the official upstream or create a fresh reference.');
    }
}

function validateCheckoutShape() {
    if (state.selectorKind === 'branch') {
        const branch = runtime.runGit(state.targetPath, ['symbolic-ref', '--quiet', '--short', 'HEAD']);
        const branchName = branch.code === 0 ? branch.output.trim() : '';
        if (branchName !== state.resolvedRef) {
            fail(1, 'current branch is ' + branchName + ', but selector requires branch ' + state.resolvedRef, 'Check out the requested branch manually or use a fresh reference; the manager will not replace the current branch.');
        }
        const upstream = runtime.runGit(state.targetPath, ['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}']);
        let upstreamName = upstream.code === 0 ? upstream.output.trim() : '';
        if (!upstreamName) {
            const configuredRemote = runtime.runGit(state.targetPath, ['config', '--get', 'branch.' + state.resolvedRef + '.remote']);
            const configuredMerge = runtime.runGit(state.targetPath, ['config', '--get', 'branch.' + state.resolvedRef + '.merge']);
            if (
                configuredRemote.code === 0 && configuredRemote.output.trim() === 'origin' &&
                configuredMerge.code === 0 && configuredMerge.output.trim() === 'refs/heads/' + state.resolvedRef
            ) {
                upstreamName = 'origin/' + state.resolvedRef;
            }
        }
        if (upstreamName !== 'origin/' + state.resolvedRef) {
            fail(1, 'current branch does not track origin/' + state.resolvedRef, 'Repair the tracking configuration manually or create a fresh reference; the manager will not rewrite it.');
        }
        return;
    }
    if (state.selectorKind === 'release' || state.selectorKind === 'tag' || state.selectorKind === 'commit') {
        const headReference = runtime.runGit(state.targetPath, ['symbolic-ref', '--quiet', '--short', 'HEAD']);
        if (headReference.code === 0) {
            fail(1, 'fixed selector requires detached HEAD', 'Detach HEAD manually at the intended reference or create a fresh fixed-reference checkout.');
        }
        return;
    }
    fail(1, 'unsupported selector kind: ' + state.selectorKind, 'Use latest, tag:REF, branch:REF, or commit:SHA.');
}

function loadLockState() {
    if (!fs.existsSync(state.lockFile)) {
        fail(1, 'offline validation requires the sibling lock state: ' + state.lockFile, 'Run an online check or update once, then retry offline.');
    }
    const lockSelector = readKeyValue(state.lockFile, 'selector');
    const lockTag = readKeyValue(state.lockFile, 'resolved_tag');
    const lockCommit = readKeyValue(state.lockFile, 'resolved_commit');
    const lockChecked = readKeyValue(state.lockFile, 'checked_at');
    const lockRepository = readKeyValue(state.lockFile, 'repository');
    if (!lockSelector || !hasKey(state.lockFile, 'resolved_tag') || !lockCommit || !lockChecked) {
        fail(1, 'lock state is incomplete: ' + state.lockFile, 'Run an online check to rebuild the lock state after inspecting the checkout.');
    }
    if (!validCheckedAt(lockChecked)) {
        fail(1, 'lock state contains an invalid checked_at value', 'Run an online check to rebuild the lock state.');
    }
    if (lockSelector !== state.selector) {
        fail(1, 'lock selector ' + lockSelector + ' does not match requested selector ' + state.selector, 'Use the locked selector, run an online update for the requested selector, or inspect the lock manually.');
    }
    if (!/^[0-9a-fA-F]{40}$/.test(lockCommit)) {
        fail(1, 'lock state contains an invalid resolved commit', 'Run an online check to rebuild the lock state.');
    }
    if (state.selectorKind === 'commit' && lockCommit.toLowerCase() !== state.resolvedRef.toLowerCase()) {
        fail(1, 'lock commit does not match the commit selector ' + state.selector, 'Run an online check for the requested commit or inspect the lock manually.');
    }
    if (lockRepository && canonicalRepository(lockRepository) !== canonicalRepository(state.repository)) {
        fail(1, 'lock state repository does not match the official ModdingAPI repository', 'Run an online check after correcting the lock state or create a fresh reference.');
    }
    if (state.selector === 'latest' && !lockTag) {
        fail(1, 'latest lock state has no resolved tag', 'Run an online check to rebuild the lock state.');
    }
    if (state.selector.startsWith('tag:') && lockTag !== state.selector.slice(4)) {
        fail(1, 'lock tag ' + lockTag + ' does not match requested selector ' + state.selector, 'Run an online update for the requested tag or inspect the lock manually.');
    }
    state.resolvedCommit = lockCommit;
    state.resolvedTag = lockTag;
}

function resolveOnline() {
    if (isTestMode() && (state.testNetworkFailure || process.env.MODDING_API_TEST_NETWORK_FAILURE === '1')) {
        state.networkState = 'offline';
        state.resolverError = 'simulated network failure for repository-owned tests';
        return false;
    }
    const metadata = state.metadataFile ? lockState.normalizePath(state.metadataFile) : '';
    const result = runtime.runResolver(SCRIPT_DIR, state.selector, metadata);
    if (result.code !== 0) {
        state.resolverError = result.output;
        state.networkState = runtime.networkFailure(result.output) ? 'offline' : 'unavailable';
        return false;
    }
    const values = runtime.resolverValues(result.output);
    state.repository = values.MODDING_API_REPOSITORY || '';
    state.selectorKind = values.MODDING_API_SELECTOR_KIND || '';
    state.resolvedRef = values.MODDING_API_RESOLVED_REF || '';
    state.resolvedTag = values.MODDING_API_RESOLVED_TAG || '';
    state.resolvedCommit = values.MODDING_API_RESOLVED_COMMIT || '';
    if (!state.repository || !state.selectorKind || !state.resolvedCommit) {
        state.networkState = 'unavailable';
        state.resolverError = 'resolver returned incomplete reference metadata';
        return false;
    }
    state.networkState = 'online';
    if (testRepository()) {
        state.repository = testRepository();
    }
    return true;
}

function runGitOrFail(args) {
    const result = runtime.runGit(state.targetPath, args);
    if (result.code !== 0) {
        state.networkState = runtime.networkFailure(result.output) ? 'offline' : 'unavailable';
        fail(1, 'Git operation failed: ' + result.output.trim(), 'Check network access and the selector; retry without changing the checkout manually.');
    }
    return result;
}

function writeResult(lockMatch, checkoutChanged, lockUpdated, checkedAt) {
    process.stdout.write(
        'MODDING_API_OPERATION=' + state.operation + '\n' +
        'MODDING_API_REFERENCE_PATH=' + state.targetPath + '\n' +
        'MODDING_API_LOCK_PATH=' + state.lockFile + '\n' +
        'MODDING_API_SELECTOR=' + state.selector + '\n' +
        'MODDING_API_SELECTOR_KIND=' + state.selectorKind + '\n' +
        'MODDING_API_RESOLVED_REF=' + state.resolvedRef + '\n' +
        'MODDING_API_RESOLVED_TAG=' + state.resolvedTag + '\n' +
        'MODDING_API_RESOLVED_COMMIT=' + state.resolvedCommit + '\n' +
        'MODDING_API_NETWORK=' + state.networkState + '\n' +
        'MODDING_API_DRY_RUN=' + boolText(state.dryRun) + '\n' +
        'MODDING_API_LOCK_MATCH=' + boolText(lockMatch) + '\n' +
        'MODDING_API_CHECKOUT_CHANGED=' + boolText(checkoutChanged) + '\n' +
        'MODDING_API_LOCK_UPDATED=' + boolText(lockUpdated) + '\n' +
        'MODDING_API_CHECKED_AT=' + checkedAt + '\n'
    );
}

function main(argv) {
    if (!parseArgs(argv)) {
        return;
    }
    validateNodeRuntime();
    if (!state.operation) {
        fail(2, 'an explicit operation is required', 'Use --operation check or --operation update.');
    }
    if (state.operation !== 'check' && state.operation !== 'update') {
        fail(2, 'invalid operation: ' + state.operation, 'Use --operation check or --operation update.');
    }
    if (state.scope && state.scope !== 'project' && state.scope !== 'user') {
        fail(2, 'invalid scope: ' + state.scope, 'Use --scope project or --scope user.');
    }
    validateTestOverrides();

    const defaults = selectDefaultPaths();
    readPreferencePath(defaults.defaultTarget);
    readSelector();
    validateSelectorSyntax();

    if (testRepository()) {
        state.repository = testRepository();
    }
    const resolverName = process.platform === 'win32' ? 'resolve_modding_api.ps1' : 'resolve_modding_api.sh';
    if (!fs.existsSync(path.join(SCRIPT_DIR, resolverName))) {
        fail(1, 'resolver script is missing', 'Reinstall the skill package and retry.');
    }

    loadCheckoutState();

    let offlineValidation = false;
    if (state.offline) {
        state.networkState = 'offline';
        offlineValidation = true;
    }
    else if (!resolveOnline()) {
        if (state.operation === 'check' && state.networkState === 'offline') {
            process.stderr.write(state.resolverError + '\n');
            offlineValidation = true;
        }
        else {
            process.stderr.write(state.resolverError + '\n');
            fail(1, 'selector resolution failed', 'Restore network access or provide a matching local lock state for an offline check.');
        }
    }

    if (offlineValidation) {
        if (state.operation !== 'check') {
            fail(1, 'update cannot refresh a reference while offline', 'Run check --offline to validate the locked checkout, then retry update online.');
        }
        loadLockState();
        validateCheckoutShape();
        if (state.currentHead !== state.resolvedCommit) {
            fail(1, 'current HEAD ' + state.currentHead + ' does not match locked commit ' + state.resolvedCommit, 'Run an online update or inspect the checkout and lock state manually.');
        }
        writeResult(true, false, false, readKeyValue(state.lockFile, 'checked_at'));
        return;
    }

    validateCheckoutShape();

    if (state.operation === 'check') {
        if (state.currentHead !== state.resolvedCommit) {
            fail(1, 'current HEAD ' + state.currentHead + ' does not match resolved commit ' + state.resolvedCommit, 'Run the explicit update operation; check never changes the checkout.');
        }
        let lockMatch = false;
        if (fs.existsSync(state.lockFile)) {
            lockMatch =
                readKeyValue(state.lockFile, 'selector') === state.selector &&
                hasKey(state.lockFile, 'resolved_tag') &&
                readKeyValue(state.lockFile, 'resolved_tag') === state.resolvedTag &&
                readKeyValue(state.lockFile, 'resolved_commit') === state.resolvedCommit &&
                (state.selectorKind !== 'commit' || state.resolvedCommit.toLowerCase() === state.resolvedRef.toLowerCase()) &&
                validCheckedAt(readKeyValue(state.lockFile, 'checked_at')) &&
                canonicalRepository(readKeyValue(state.lockFile, 'repository')) === canonicalRepository(state.repository);
        }
        let lockUpdated = false;
        let checkedAt = readKeyValue(state.lockFile, 'checked_at');
        if (!lockMatch) {
            if (state.dryRun) {
                checkedAt = '<not-written>';
            }
            else {
                checkedAt = lockState.utcNow();
                try {
                    lockState.writeLockState(state.lockFile, state.selector, state.resolvedTag, state.resolvedCommit, state.repository, checkedAt);
                }
                catch (error) {
                    fail(1, 'could not write lock state: ' + state.lockFile, 'Ensure the references directory is writable, then rerun check.');
                }
                lockUpdated = true;
            }
        }
        writeResult(state.dryRun ? lockMatch : true, false, lockUpdated, checkedAt);
        return;
    }

    let checkoutChanged = false;
    if (state.dryRun) {
        let planRequiresFetch = false;
        if (state.selectorKind === 'branch') {
            const remoteRef = 'refs/remotes/origin/' + state.resolvedRef;
            const remote = runtime.runGit(state.targetPath, ['rev-parse', '--verify', remoteRef]);
            if (remote.code === 0 && remote.output.trim()) {
                if (
                    state.currentHead !== remote.output.trim() &&
                    runtime.runGit(state.targetPath, ['merge-base', '--is-ancestor', 'HEAD', remoteRef]).code !== 0
                ) {
                    fail(1, 'local branch history is divergent from origin/' + state.resolvedRef, 'Reconcile the branch manually; the manager will not reset, stash, or delete local history.');
                }
            }
            else {
                planRequiresFetch = true;
            }
            checkoutChanged = state.currentHead !== state.resolvedCommit;
        }
        else {
            checkoutChanged = state.currentHead !== state.resolvedCommit;
        }
        writeResult(false, checkoutChanged, false, '<not-written>');
        process.stdout.write('MODDING_API_PLAN_REQUIRES_FETCH=' + boolText(planRequiresFetch) + '\n');
        return;
    }

    if (state.selectorKind === 'branch') {
        const shallow = runtime.runGit(state.targetPath, ['rev-parse', '--is-shallow-repository']);
        const refspec = '+refs/heads/' + state.resolvedRef + ':refs/remotes/origin/' + state.resolvedRef;
        if (shallow.code === 0 && shallow.output.trim() === 'true') {
            runGitOrFail(['fetch', '--unshallow', 'origin', refspec]);
        }
        else {
            runGitOrFail(['fetch', 'origin', refspec]);
        }
        const remoteRef = 'refs/remotes/origin/' + state.resolvedRef;
        const remote = runtime.runGit(state.targetPath, ['rev-parse', '--verify', remoteRef]);
        const remoteCommit = remote.code === 0 ? remote.output.trim() : '';
        if (!remoteCommit) {
            fail(1, 'requested branch ref is missing after fetch: ' + state.resolvedRef, 'Verify the branch name and retry; no checkout or lock change was performed.');
        }
        if (remoteCommit !== state.resolvedCommit) {
            fail(1, 'resolved branch commit changed during update', 'Retry the update so the selector can be resolved and fetched consistently.');
        }
        if (state.currentHead !== remoteCommit) {
        const ancestor = runtime.runGit(state.targetPath, ['merge-base', '--is-ancestor', 'HEAD', remoteRef]);
            if (ancestor.code !== 0) {
                fail(1, 'local branch history is divergent from origin/' + state.resolvedRef, 'Reconcile the branch manually; the manager will not reset, stash, or delete local history.');
            }
            runGitOrFail(['merge', '--ff-only', remoteRef]);
            checkoutChanged = true;
        }
    }
    else if (state.currentHead !== state.resolvedCommit) {
        runGitOrFail(['fetch', '--depth', '1', 'origin', state.resolvedCommit]);
        runGitOrFail(['checkout', '--detach', state.resolvedCommit]);
        checkoutChanged = true;
    }

    state.currentHead = currentHead();
    if (state.currentHead !== state.resolvedCommit) {
        fail(1, 'update ended at ' + state.currentHead + ' instead of resolved commit ' + state.resolvedCommit, 'Inspect the checkout manually; no destructive recovery was attempted.');
    }
    validateCheckoutShape();
    const checkedAt = lockState.utcNow();
    try {
        lockState.writeLockState(state.lockFile, state.selector, state.resolvedTag, state.resolvedCommit, state.repository, checkedAt);
    }
    catch (error) {
        fail(1, 'checkout updated but lock state could not be written: ' + state.lockFile, 'Write the resolved selector and commit to the sibling lock file, then run check.');
    }
    writeResult(true, checkoutChanged, true, checkedAt);
}

try {
    main(process.argv.slice(2));
}
catch (error) {
    if (error instanceof Stop) {
        process.exitCode = error.code;
    }
    else {
        state.networkState = runtime.networkFailure(error && error.message) ? 'offline' : 'unavailable';
        process.exitCode = printErrorReport(1, error && error.message ? error.message : text(error), 'Inspect the error and retry without changing the checkout.');
    }
}
