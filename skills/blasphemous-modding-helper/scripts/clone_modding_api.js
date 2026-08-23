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
    scope: '',
    targetPath: '',
    preferencesFile: '',
    selector: '',
    metadataFile: '',
    selectorExplicit: false,
    targetExplicit: false,
    preferencesExplicit: false,
    testMode: false,
    testRepository: '',
    testHome: '',
    networkState: 'unknown'
};

class Stop extends Error {
    constructor(code, cause, nextStep) {
        super(cause);
        this.code = code;
        this.cause = cause;
        this.nextStep = nextStep;
    }
}

function text(value) {
    return value === undefined || value === null ? '' : String(value);
}

function pathExists(file) {
    try {
        fs.lstatSync(file);
        return true;
    }
    catch (error) {
        if (error && error.code === 'ENOENT') {
            return false;
        }
        throw error;
    }
}

function cloneCurrentHead() {
    try {
        if (!state.targetPath || !pathExists(state.targetPath)) {
            return '<unavailable>';
        }
        const result = runtime.runGit(state.targetPath, ['rev-parse', 'HEAD']);
        return result.code === 0 ? result.output.trim().split(/\r?\n/)[0] : '<unavailable>';
    }
    catch (error) {
        return '<unavailable>';
    }
}

function cloneWorktreeState() {
    try {
        if (!state.targetPath || !pathExists(state.targetPath)) {
            return 'missing';
        }
        const inside = runtime.runGit(state.targetPath, ['rev-parse', '--is-inside-work-tree']);
        if (inside.code !== 0 || inside.output.trim() !== 'true') {
            return 'not-a-git-worktree';
        }
        const status = runtime.runGit(state.targetPath, ['status', '--porcelain', '--untracked-files=all']);
        return status.code === 0 ? (status.output.trim() ? 'dirty' : 'clean') : 'unknown';
    }
    catch (error) {
        return 'unknown';
    }
}

function usage() {
    process.stdout.write(
        'Usage:\n' +
        '  clone_modding_api --scope project|user [options]\n\n' +
        'Options:\n' +
        '  --scope project|user      Use the approved project or user reference path.\n' +
        '  --target-path PATH        Override the reference checkout path.\n' +
        '  --preferences-file PATH   Write the selected path and selector to preferences.md.\n' +
        '  --selector SELECTOR       latest, tag:REF, branch:REF, or commit:SHA.\n' +
        '  --metadata-file PATH      Test-only resolver metadata fixture.\n' +
        '  --help                    Show this help.\n\n' +
        'Existing targets and sibling lock paths are never replaced.\n'
    );
}

function printErrorReport(code, cause, nextStep) {
    process.stderr.write(
        '[ERROR REPORT]\n' +
        'operation: clone_modding_api\n' +
        'target_path: ' + (state.targetPath || '<unset>') + '\n' +
        'selector: ' + (state.selector || '<unset>') + '\n' +
        'current_head: ' + cloneCurrentHead() + '\n' +
        'worktree_state: ' + cloneWorktreeState() + '\n' +
        'network_state: ' + state.networkState + '\n' +
        'cause: ' + cause + '\n' +
        'next_step: ' + nextStep + '\n'
    );
    return code;
}

function fail(code, cause, nextStep) {
    if (runtime.networkFailure(cause)) {
        state.networkState = 'failed';
    }
    throw new Stop(code, cause, nextStep);
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
            case '--test-mode':
                state.testMode = true;
                break;
            case '--test-repository':
                state.testRepository = value();
                break;
            case '--test-home':
                state.testHome = value();
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

function readKeyValue(file, key) {
    if (!file || !fs.existsSync(file)) {
        return '';
    }
    const escapedKey = key.replace(/[|\\{}()[\]^$+*?.-]/g, '\\$&');
    const pattern = new RegExp('^[ \\t]*' + escapedKey + '[ \\t]*:[ \\t]*(.*)$');
    for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
        const match = line.match(pattern);
        if (match) {
            return match[1].trim();
        }
    }
    return '';
}

function isTestMode() {
    return state.testMode || process.env.MODDING_API_TEST_MODE === '1';
}

function testRepository() {
    return state.testRepository || process.env.MODDING_API_TEST_REPOSITORY || '';
}

function testHome() {
    return state.testHome || process.env.MODDING_API_TEST_HOME || '';
}

function validateNodeRuntime() {
    const major = Number(process.versions.node.split('.')[0]);
    if (!Number.isInteger(major) || major < 18) {
        fail(1, 'Node.js 18 or newer is required to create a local reference', 'Install Node.js 18 or newer and retry.');
    }
}

function validateTestOverrides() {
    if ((state.metadataFile || testRepository()) && !isTestMode()) {
        fail(2, 'resolver fixtures and repository overrides require test mode', 'Use the official resolver without fixtures, or run repository-owned tests with MODDING_API_TEST_MODE=1.');
    }
}

function runGitChecked(cwd, args) {
    const result = runtime.runGit(cwd, args);
    if (result.code !== 0) {
        if (runtime.networkFailure(result.output)) {
            state.networkState = 'failed';
        }
        fail(1, 'Git operation failed: ' + result.output.trim(), 'Check network access, the selector, and the target path.');
    }
    return result;
}

function selectDefaultPaths() {
    const cwd = process.cwd();
    const home = isTestMode() && testHome() ? testHome() : os.homedir();
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

function selectTarget(defaultTarget) {
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

function selectSelector() {
    if (!state.selectorExplicit) {
        const configuredSelector = readKeyValue(state.preferencesFile, 'modding_api_reference_selector');
        state.selector = configuredSelector || 'latest';
    }
    if (!state.selector) {
        fail(2, 'no selector was configured', 'Use --selector or add modding_api_reference_selector to preferences.md.');
    }
}

function validateSelector() {
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
    if (match && /^[0-9a-fA-F]{40}$/.test(match[1])) {
        state.selectorKind = 'commit';
        state.resolvedRef = match[1];
        return;
    }
    fail(2, 'invalid selector: ' + state.selector, 'Use latest, tag:REF, branch:REF, or commit:SHA.');
}

function localRepositoryPath(repository) {
    if (/^(?:[A-Za-z]:[\\/]|\/)/.test(repository)) {
        return lockState.normalizePath(repository);
    }
    return repository;
}

function writePreferences(file, referencePath, selector) {
    const parent = path.dirname(file);
    fs.mkdirSync(parent, { recursive: true });
    const existing = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : '';
    const lines = existing ? existing.split(/\r?\n/) : [];
    const output = [];
    let pathSeen = false;
    let selectorSeen = false;
    for (const line of lines) {
        if (/^\s*modding_api_reference_path\s*:/.test(line)) {
            output.push('modding_api_reference_path: ' + referencePath);
            pathSeen = true;
        }
        else if (/^\s*modding_api_reference_selector\s*:/.test(line)) {
            output.push('modding_api_reference_selector: ' + selector);
            selectorSeen = true;
        }
        else if (line !== '' || output.length > 0) {
            output.push(line);
        }
    }
    if (!pathSeen) {
        output.push('modding_api_reference_path: ' + referencePath);
    }
    if (!selectorSeen) {
        output.push('modding_api_reference_selector: ' + selector);
    }
    lockState.atomicWriteFile(file, output.join('\n') + '\n');
}

function acquireCommitGuard(parent) {
    const guardPath = path.join(parent, '.' + path.basename(state.targetPath) + '.clone-lock');
    try {
        fs.mkdirSync(guardPath);
    }
    catch (error) {
        if (error && error.code === 'EEXIST') {
            fail(1, 'another clone operation is already using the target path', 'Wait for the other operation to finish or remove the stale clone lock after confirming no clone is running.');
        }
        throw error;
    }
    return guardPath;
}

function releaseCommitGuard(guardPath) {
    const errors = [];
    if (!guardPath) {
        return errors;
    }
    try {
        if (pathExists(guardPath)) {
            fs.rmSync(guardPath, { recursive: true, force: true });
        }
    }
    catch (error) {
        errors.push('clone lock cleanup: ' + text(error && error.message ? error.message : error));
    }
    return errors;
}

function cleanupStaging(stagingPath, lockStagingPath) {
    const errors = [];
    const attempt = (action, label) => {
        try {
            action();
        }
        catch (error) {
            errors.push(label + ': ' + text(error && error.message ? error.message : error));
        }
    };
    if (stagingPath) {
        attempt(() => { if (pathExists(stagingPath)) fs.rmSync(stagingPath, { recursive: true, force: true }); }, 'staging checkout cleanup');
    }
    if (lockStagingPath) {
        attempt(() => { if (pathExists(lockStagingPath)) fs.rmSync(lockStagingPath, { force: true }); }, 'staging lock cleanup');
    }
    return errors;
}

function pathIdentity(file) {
    const stat = fs.lstatSync(file);
    return {
        dev: stat.dev,
        ino: stat.ino,
        birthtimeMs: stat.birthtimeMs,
        mode: stat.mode
    };
}

function samePathIdentity(file, identity) {
    try {
        const current = pathIdentity(file);
        return current.dev === identity.dev &&
            current.ino === identity.ino &&
            current.birthtimeMs === identity.birthtimeMs &&
            current.mode === identity.mode;
    }
    catch (error) {
        return false;
    }
}

function reserveDirectory(destination, label) {
    if (pathExists(destination)) {
        fail(1, label + ' path appeared during clone: ' + destination, 'Another process created the path; choose a different target or retry after inspecting it.');
    }
    try {
        fs.mkdirSync(destination);
    }
    catch (error) {
        if (error && (error.code === 'EEXIST' || error.code === 'ENOTEMPTY')) {
            fail(1, label + ' path appeared during clone: ' + destination, 'Another process created the path; choose a different target or retry after inspecting it.');
        }
        throw error;
    }
    return pathIdentity(destination);
}

function moveDirectoryContents(source, destination, destinationIdentity, movedEntries) {
    for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
        if (!samePathIdentity(destination, destinationIdentity)) {
            fail(1, 'reserved target was replaced during clone: ' + destination, 'Inspect the replacement path and retry with a fresh target.');
        }
        const sourceEntry = path.join(source, entry.name);
        const destinationEntry = path.join(destination, entry.name);
        if (pathExists(destinationEntry)) {
            fail(1, 'target checkout entry appeared during clone: ' + destinationEntry, 'Another process wrote into the reserved target; inspect it and retry with a fresh target.');
        }
        try {
            fs.cpSync(sourceEntry, destinationEntry, {
                recursive: true,
                force: false,
                errorOnExist: true,
                verbatimSymlinks: true
            });
        }
        catch (error) {
            if (pathExists(destinationEntry)) {
                fail(1, 'target checkout entry appeared during clone: ' + destinationEntry, 'Another process wrote into the reserved target; inspect it and retry with a fresh target.');
            }
            throw error;
        }
        movedEntries.push({ name: entry.name, identity: pathIdentity(destinationEntry) });
        fs.rmSync(sourceEntry, { recursive: true, force: true });
        if (!samePathIdentity(destination, destinationIdentity)) {
            fail(1, 'reserved target was replaced during clone: ' + destination, 'Inspect the replacement path and retry with a fresh target.');
        }
    }
}

function writeExclusiveLock(source, destination) {
    const content = fs.readFileSync(source, 'utf8');
    let descriptor = null;
    let created = false;
    try {
        descriptor = fs.openSync(destination, 'wx');
        created = true;
        fs.writeFileSync(descriptor, content, 'utf8');
        fs.fsyncSync(descriptor);
    }
    catch (error) {
        if (created) {
            try {
                fs.rmSync(destination, { force: true });
            }
            catch (cleanupError) {
                error.message += ' Lock cleanup failed: ' + text(cleanupError && cleanupError.message ? cleanupError.message : cleanupError);
            }
        }
        if (error && error.code === 'EEXIST') {
            fail(1, 'lock state path appeared during clone: ' + destination, 'Another process created the sibling lock; inspect it and retry with a fresh target.');
        }
        throw error;
    }
    finally {
        if (descriptor !== null) {
            fs.closeSync(descriptor);
        }
    }
}

function linkNoReplace(source, destination) {
    try {
        fs.linkSync(source, destination);
        return;
    }
    catch (error) {
        if (error && error.code === 'EEXIST') {
            fail(1, 'lock state path appeared during clone: ' + destination, 'Another process created the sibling lock; inspect it and retry with a fresh target.');
        }
        if (!error || !['EPERM', 'EOPNOTSUPP', 'ENOSYS'].includes(error.code)) {
            throw error;
        }
    }
    writeExclusiveLock(source, destination);
}

function rollback(targetMoved, targetIdentity, lockMoved, preferencesChanged, preferencesExisted, preferencesContent, movedEntries) {
    const errors = [];
    const attempt = (action, label) => {
        try {
            action();
        }
        catch (error) {
            errors.push(label + ': ' + text(error && error.message ? error.message : error));
        }
    };
    if (lockMoved) {
        attempt(() => { if (pathExists(state.lockFile)) fs.rmSync(state.lockFile, { force: true }); }, 'lock cleanup');
    }
    if (targetMoved) {
        attempt(() => {
            if (!pathExists(state.targetPath)) {
                return;
            }
            if (!targetIdentity || !samePathIdentity(state.targetPath, targetIdentity)) {
                throw new Error('reserved target was replaced during clone');
            }
            for (const entry of movedEntries.slice().reverse()) {
                const targetEntry = path.join(state.targetPath, entry.name);
                if (pathExists(targetEntry)) {
                    if (!samePathIdentity(targetEntry, entry.identity)) {
                        throw new Error('checkout entry was replaced during cleanup: ' + targetEntry);
                    }
                    fs.rmSync(targetEntry, { recursive: true, force: true });
                }
            }
            if (!samePathIdentity(state.targetPath, targetIdentity)) {
                throw new Error('reserved target was replaced during checkout cleanup');
            }
            const remaining = fs.readdirSync(state.targetPath);
            if (remaining.length > 0) {
                throw new Error('checkout cleanup left concurrent entries: ' + remaining.join(', '));
            }
            fs.rmdirSync(state.targetPath);
        }, 'checkout cleanup');
    }
    if (preferencesChanged) {
        if (preferencesExisted) {
            attempt(() => lockState.atomicWriteFile(state.preferencesFile, preferencesContent), 'preferences restore');
        }
        else {
            attempt(() => { if (pathExists(state.preferencesFile)) fs.rmSync(state.preferencesFile, { force: true }); }, 'preferences cleanup');
        }
    }
    return errors;
}

function main(argv) {
    if (!parseArgs(argv)) {
        return;
    }
    validateNodeRuntime();
    if (state.scope && state.scope !== 'project' && state.scope !== 'user') {
        fail(2, 'invalid scope: ' + state.scope, 'Use --scope project or --scope user.');
    }
    validateTestOverrides();
    if (!fs.existsSync(path.join(SCRIPT_DIR, process.platform === 'win32' ? 'resolve_modding_api.ps1' : 'resolve_modding_api.sh'))) {
        fail(1, 'resolver script is missing', 'Reinstall the skill package and retry.');
    }

    const defaults = selectDefaultPaths();
    selectTarget(defaults.defaultTarget);
    selectSelector();
    validateSelector();
    const parent = path.dirname(state.targetPath);
    fs.mkdirSync(parent, { recursive: true });
    let guardPath = '';
    let stagingPath = '';
    let lockStagingPath = '';
    let targetMoved = false;
    let targetIdentity = null;
    let lockMoved = false;
    let movedEntries = [];
    let preferencesExisted = false;
    let preferencesContent = '';
    let preferencesChanged = false;
    let checkedAt = '';
    let selectorKind = '';
    let resolvedRef = '';
    let resolvedTag = '';
    let resolvedCommit = '';
    try {
        guardPath = acquireCommitGuard(parent);
        if (pathExists(state.targetPath)) {
            fail(2, 'target path already exists: ' + state.targetPath, 'Choose a missing directory or use the later update/check workflow.');
        }
        if (pathExists(state.lockFile)) {
            fail(2, 'lock path already exists: ' + state.lockFile, 'Inspect or remove the stale lock manually, then retry with a fresh target.');
        }
        const metadataFile = state.metadataFile ? lockState.normalizePath(state.metadataFile) : '';
        const resolved = runtime.runResolver(SCRIPT_DIR, state.selector, metadataFile);
        if (resolved.code !== 0) {
            if (runtime.networkFailure(resolved.output)) {
                state.networkState = 'failed';
            }
            process.stderr.write(resolved.output + (resolved.output.endsWith('\n') ? '' : '\n'));
            fail(1, 'selector resolution failed', 'Fix the selector or network/Release metadata problem, then retry.');
        }
        const values = runtime.resolverValues(resolved.output);
        const repositoryFromResolver = values.MODDING_API_REPOSITORY || '';
        selectorKind = values.MODDING_API_SELECTOR_KIND || '';
        resolvedRef = values.MODDING_API_RESOLVED_REF || '';
        resolvedTag = values.MODDING_API_RESOLVED_TAG || '';
        resolvedCommit = values.MODDING_API_RESOLVED_COMMIT || '';
        if (!repositoryFromResolver || !selectorKind || !resolvedRef || !resolvedCommit) {
            fail(1, 'resolver returned incomplete reference metadata', 'Retry the selector resolution and inspect its error report.');
        }
        state.repository = testRepository() || repositoryFromResolver;
        const repositoryForGit = localRepositoryPath(state.repository);
        stagingPath = fs.mkdtempSync(path.join(parent, '.' + path.basename(state.targetPath) + '.staging-'));
        lockStagingPath = path.join(parent, '.' + path.basename(state.lockFile) + '.staging-' + Math.random().toString(16).slice(2));
        preferencesExisted = Boolean(state.preferencesFile && pathExists(state.preferencesFile));
        preferencesContent = preferencesExisted ? fs.readFileSync(state.preferencesFile, 'utf8') : '';
        runGitChecked(stagingPath, ['init', '-q']);
        runGitChecked(stagingPath, ['remote', 'add', 'origin', repositoryForGit]);
        if (selectorKind === 'release' || selectorKind === 'tag') {
            runGitChecked(stagingPath, ['fetch', '--depth', '1', 'origin', 'refs/tags/' + resolvedRef + ':refs/tags/' + resolvedRef]);
            runGitChecked(stagingPath, ['checkout', '--detach', 'refs/tags/' + resolvedRef]);
        }
        else if (selectorKind === 'branch') {
            runGitChecked(stagingPath, ['fetch', '--depth', '1', 'origin', 'refs/heads/' + resolvedRef + ':refs/remotes/origin/' + resolvedRef]);
            runGitChecked(stagingPath, ['checkout', '-q', '-b', resolvedRef, '--track', 'refs/remotes/origin/' + resolvedRef]);
        }
        else if (selectorKind === 'commit') {
            runGitChecked(stagingPath, ['fetch', '--depth', '1', 'origin', resolvedCommit]);
            runGitChecked(stagingPath, ['checkout', '--detach', resolvedCommit]);
        }
        else {
            fail(1, 'resolver returned unsupported selector kind: ' + selectorKind, 'Use latest, tag:REF, branch:REF, or commit:SHA.');
        }
        const actualCommit = runGitChecked(stagingPath, ['rev-parse', 'HEAD']).output.trim();
        if (actualCommit !== resolvedCommit) {
            fail(1, 'checkout resolved to ' + actualCommit + ' instead of ' + resolvedCommit, 'Retry the clone and inspect the selected Git reference.');
        }
        if (!pathExists(path.join(stagingPath, '.git', 'shallow'))) {
            fail(1, 'clone is not shallow', 'Retry with a Git installation that supports shallow fetches.');
        }
        if (selectorKind === 'branch') {
            const upstream = runGitChecked(stagingPath, ['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}']).output.trim();
            if (upstream !== 'origin/' + resolvedRef) {
                fail(1, 'branch does not track origin/' + resolvedRef, 'Retry the fresh clone with the requested branch selector.');
            }
        }
        else if (runtime.runGit(stagingPath, ['symbolic-ref', '--quiet', '--short', 'HEAD']).code === 0) {
            fail(1, 'fixed reference is not detached', 'Retry the fresh clone with the requested tag or commit selector.');
        }
        checkedAt = lockState.utcNow();
        lockState.writeLockState(lockStagingPath, state.selector, resolvedTag, resolvedCommit, state.repository, checkedAt);
        targetIdentity = reserveDirectory(state.targetPath, 'target checkout');
        targetMoved = true;
        moveDirectoryContents(stagingPath, state.targetPath, targetIdentity, movedEntries);
        fs.rmdirSync(stagingPath);
        stagingPath = '';
        if (state.preferencesFile) {
            preferencesChanged = true;
            writePreferences(state.preferencesFile, state.targetPath, state.selector);
        }
        linkNoReplace(lockStagingPath, state.lockFile);
        lockMoved = true;
    }
    catch (error) {
        const rollbackErrors = rollback(targetMoved, targetIdentity, lockMoved, preferencesChanged, preferencesExisted, preferencesContent, movedEntries);
        const cleanupErrors = cleanupStaging(stagingPath, lockStagingPath);
        const guardErrors = releaseCommitGuard(guardPath);
        const rollbackReport = rollbackErrors.concat(cleanupErrors, guardErrors);
        if (error instanceof Stop) {
            if (rollbackReport.length > 0) {
                error.nextStep += ' Rollback also failed: ' + rollbackReport.join('; ');
            }
        }
        else {
            fail(1, 'clone operation failed: ' + text(error && error.message ? error.message : error), rollbackReport.length > 0 ? 'Rollback failed: ' + rollbackReport.join('; ') : 'Inspect the target path and retry.');
        }
        throw error;
    }
    const finalizationErrors = cleanupStaging(stagingPath, lockStagingPath).concat(releaseCommitGuard(guardPath));
    if (finalizationErrors.length > 0) {
        fail(1, 'clone completed but cleanup failed', 'Inspect the checkout and lock state, then remove only confirmed staging or clone-lock artifacts. Details: ' + finalizationErrors.join('; '));
    }
    process.stdout.write(
        'MODDING_API_OPERATION=clone\n' +
        'MODDING_API_REPOSITORY=' + state.repository + '\n' +
        'MODDING_API_REFERENCE_PATH=' + state.targetPath + '\n' +
        'MODDING_API_PREFERENCES_FILE=' + state.preferencesFile + '\n' +
        'MODDING_API_SELECTOR=' + state.selector + '\n' +
        'MODDING_API_SELECTOR_KIND=' + selectorKind + '\n' +
        'MODDING_API_RESOLVED_REF=' + resolvedRef + '\n' +
        'MODDING_API_RESOLVED_TAG=' + resolvedTag + '\n' +
        'MODDING_API_RESOLVED_COMMIT=' + resolvedCommit + '\n' +
        'MODDING_API_SHALLOW=true\n' +
        'MODDING_API_LOCK_PATH=' + state.lockFile + '\n' +
        'MODDING_API_CHECKED_AT=' + checkedAt + '\n'
    );
}

try {
    main(process.argv.slice(2));
}
catch (error) {
    if (error instanceof Stop) {
        process.exitCode = printErrorReport(error.code, error.cause, error.nextStep);
    }
    else {
        process.exitCode = printErrorReport(1, text(error && error.message ? error.message : error), 'Inspect the error and retry.');
    }
}
