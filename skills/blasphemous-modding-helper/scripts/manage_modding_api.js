#!/usr/bin/env node
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const lockState = require('./modding_api_lock');
const runtime = require('./modding_api_runtime');
const lifecycle = require('./modding_api_lifecycle');

const SCRIPT_DIR = __dirname;
const OFFICIAL_REPOSITORY = lifecycle.OFFICIAL_REPOSITORY;
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

function reportCheckout() {
    try {
        const inspection = lifecycle.inspectCheckout({
            fileSystem: fs,
            targetPath: state.targetPath,
            runGit: runtime.runGit,
            repository: state.repository
        });
        return {
            currentHead: inspection.currentHead || '<unavailable>',
            worktreeState: inspection.worktreeState || 'unknown'
        };
    }
    catch (error) {
        return { currentHead: '<unavailable>', worktreeState: 'unknown' };
    }
}

function printErrorReport(code, cause, nextStep) {
    const checkout = reportCheckout();
    process.stderr.write(
        '[ERROR REPORT]\n' +
        'operation: ' + (state.operation || '<unset>') + '\n' +
        'target_path: ' + (state.targetPath || '<unset>') + '\n' +
        'selector: ' + (state.selector || '<unset>') + '\n' +
        'current_head: ' + checkout.currentHead + '\n' +
        'worktree_state: ' + checkout.worktreeState + '\n' +
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
    const context = lifecycle.selectPreferenceContext({
        cwd: cwd,
        home: home,
        scope: state.scope,
        preferencesFile: state.preferencesFile,
        targetExplicit: state.targetExplicit,
        preferencesExplicit: state.preferencesExplicit,
        pathModule: path,
        fileSystem: fs,
        normalizePath: lockState.normalizePath
    });
    if (!context.ok) {
        fail(context.code, context.cause, context.nextStep);
    }
    state.preferencesFile = context.preferencesFile;
    return context;
}

function readPreferencePath(defaultTarget) {
    const target = lifecycle.resolveTarget({
        targetPath: state.targetPath,
        targetExplicit: state.targetExplicit,
        preferencesFile: state.preferencesFile,
        defaultTarget: defaultTarget,
        fileSystem: fs,
        normalizePath: lockState.normalizePath
    });
    if (!target.ok) {
        fail(target.code, target.cause, target.nextStep);
    }
    state.targetPath = target.targetPath;
    state.lockFile = target.lockFile;
}

function readSelector() {
    const selector = lifecycle.resolveSelector({
        selector: state.selector,
        selectorExplicit: state.selectorExplicit,
        preferencesFile: state.preferencesFile,
        fileSystem: fs
    });
    if (!selector.ok) {
        fail(selector.code, selector.cause, selector.nextStep);
    }
    state.selector = selector.selector;
    state.selectorKind = selector.selectorKind;
    state.resolvedRef = selector.resolvedRef;
}

function loadCheckoutState() {
    const inspection = lifecycle.inspectCheckout({
        fileSystem: fs,
        targetPath: state.targetPath,
        runGit: runtime.runGit,
        repository: state.repository
    });
    state.currentHead = inspection.currentHead || '<unavailable>';
    state.worktreeState = inspection.worktreeState || 'unknown';
    if (!inspection.ok) {
        fail(inspection.code, inspection.cause, inspection.nextStep);
    }
}

function validateCheckoutShape() {
    const shape = lifecycle.validateCheckoutShape({
        targetPath: state.targetPath,
        selectorKind: state.selectorKind,
        resolvedRef: state.resolvedRef,
        runGit: runtime.runGit
    });
    if (!shape.ok) {
        fail(shape.code, shape.cause, shape.nextStep);
    }
}

function loadLockState() {
    const lock = lifecycle.validateLock({
        fileSystem: fs,
        lockFile: state.lockFile,
        selector: state.selector,
        selectorKind: state.selectorKind,
        resolvedRef: state.resolvedRef,
        repository: state.repository
    });
    if (!lock.ok) {
        fail(lock.code, lock.cause, lock.nextStep);
    }
    state.resolvedCommit = lock.resolvedCommit;
    state.resolvedTag = lock.resolvedTag;
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
    const values = lifecycle.parseResolverMetadata(runtime.resolverValues(result.output));
    state.repository = values.repository;
    state.selectorKind = values.selectorKind;
    state.resolvedRef = values.resolvedRef;
    state.resolvedTag = values.resolvedTag;
    state.resolvedCommit = values.resolvedCommit;
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
        writeResult(true, false, false, lifecycle.readLock(state.lockFile, fs).checkedAt);
        return;
    }

    validateCheckoutShape();

    if (state.operation === 'check') {
        if (state.currentHead !== state.resolvedCommit) {
            fail(1, 'current HEAD ' + state.currentHead + ' does not match resolved commit ' + state.resolvedCommit, 'Run the explicit update operation; check never changes the checkout.');
        }
        let lockMatch = false;
        if (fs.existsSync(state.lockFile)) {
            lockMatch = lifecycle.lockMatches({
                fileSystem: fs,
                lockFile: state.lockFile,
                selector: state.selector,
                selectorKind: state.selectorKind,
                resolvedRef: state.resolvedRef,
                resolvedTag: state.resolvedTag,
                resolvedCommit: state.resolvedCommit,
                repository: state.repository
            });
        }
        let lockUpdated = false;
        let checkedAt = lifecycle.readLock(state.lockFile, fs).checkedAt;
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

    const postUpdateInspection = lifecycle.inspectCheckout({
        fileSystem: fs,
        targetPath: state.targetPath,
        runGit: runtime.runGit,
        repository: state.repository
    });
    state.currentHead = postUpdateInspection.currentHead || '<unavailable>';
    if (!postUpdateInspection.ok) {
        fail(postUpdateInspection.code, postUpdateInspection.cause, postUpdateInspection.nextStep);
    }
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
