'use strict';

const fs = require('fs');
const path = require('path');

const OFFICIAL_REPOSITORY = 'https://github.com/BrandenEK/Blasphemous.ModdingAPI.git';

function text(value) {
    return value === undefined || value === null ? '' : String(value);
}

function failure(code, cause, nextStep, extra) {
    return Object.assign({
        ok: false,
        code: code,
        cause: cause,
        nextStep: nextStep
    }, extra || {});
}

function success(extra) {
    return Object.assign({ ok: true }, extra || {});
}

function escapeRegExp(value) {
    return text(value).replace(/[|\\{}()[\]^$+*?.-]/g, '\\$&');
}

function readKeyValue(file, key, fileSystem) {
    const io = fileSystem || fs;
    if (!file || !io.existsSync(file)) {
        return '';
    }
    const content = io.readFileSync(file, 'utf8');
    const pattern = new RegExp('^[ \\t]*' + escapeRegExp(key) + '[ \\t]*:[ \\t]*(.*)$');
    for (const line of content.split(/\r?\n/)) {
        const match = line.match(pattern);
        if (match) {
            return match[1].trim();
        }
    }
    return '';
}

function hasKey(file, key, fileSystem) {
    const io = fileSystem || fs;
    if (!file || !io.existsSync(file)) {
        return false;
    }
    const content = io.readFileSync(file, 'utf8');
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
    return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(text(value)) &&
        !Number.isNaN(Date.parse(value));
}

function parseSelector(selector, options) {
    const settings = options || {};
    const value = text(selector);
    if (value === 'latest') {
        return success({
            selector: value,
            selectorKind: 'release',
            resolvedRef: ''
        });
    }
    let match = value.match(/^tag:(.+)$/);
    if (match) {
        return success({
            selector: value,
            selectorKind: 'tag',
            resolvedRef: match[1]
        });
    }
    match = value.match(/^branch:(.+)$/);
    if (match) {
        return success({
            selector: value,
            selectorKind: 'branch',
            resolvedRef: match[1]
        });
    }
    match = value.match(/^commit:(.+)$/);
    if (match && /^[0-9a-fA-F]{40}$/.test(match[1])) {
        return success({
            selector: value,
            selectorKind: 'commit',
            resolvedRef: match[1]
        });
    }
    if (match && !/^[0-9a-fA-F]{40}$/.test(match[1]) && settings.commitError !== false) {
        return failure(
            2,
            'commit selector must contain a 40-character SHA',
            'Use commit:SHA with an exact 40-character commit.'
        );
    }
    return failure(
        2,
        'invalid selector: ' + value,
        'Use latest, tag:REF, branch:REF, or commit:SHA.'
    );
}

function selectPreferenceContext(options) {
    const settings = options || {};
    const io = settings.fileSystem || fs;
    const normalizePath = settings.normalizePath || (value => value);
    const cwd = settings.cwd || process.cwd();
    const home = settings.home || '';
    const scope = settings.scope || '';
    let preferencesFile = settings.preferencesFile || '';
    const targetExplicit = Boolean(settings.targetExplicit);
    const preferencesExplicit = Boolean(settings.preferencesExplicit);
    const pathModule = settings.pathModule || path;
    const projectTarget = pathModule.join(
        cwd,
        '.skills',
        'blasphemous-modding-helper',
        'references',
        'modding-api'
    );
    const projectPreferences = pathModule.join(
        cwd,
        '.skills',
        'blasphemous-modding-helper',
        'preferences.md'
    );
    const userTarget = pathModule.join(
        home,
        '.skills',
        'blasphemous-modding-helper',
        'references',
        'modding-api'
    );
    const userPreferences = pathModule.join(
        home,
        '.skills',
        'blasphemous-modding-helper',
        'preferences.md'
    );
    let defaultTarget = '';
    let defaultPreferences = '';

    if (scope === 'project') {
        defaultTarget = projectTarget;
        defaultPreferences = projectPreferences;
        if (!preferencesFile) {
            preferencesFile = defaultPreferences;
        }
    }
    else if (scope === 'user') {
        defaultTarget = userTarget;
        defaultPreferences = userPreferences;
        if (!preferencesFile) {
            preferencesFile = defaultPreferences;
        }
    }
    else if (!preferencesFile && !targetExplicit) {
        if (io.existsSync(projectPreferences)) {
            defaultTarget = projectTarget;
            defaultPreferences = projectPreferences;
            preferencesFile = projectPreferences;
        }
        else if (io.existsSync(userPreferences)) {
            defaultTarget = userTarget;
            defaultPreferences = userPreferences;
            preferencesFile = userPreferences;
        }
    }

    if (preferencesFile) {
        preferencesFile = normalizePath(preferencesFile);
        if (
            scope &&
            preferencesExplicit &&
            preferencesFile !== normalizePath(defaultPreferences)
        ) {
            return failure(
                2,
                'preferences file scope does not match --scope ' + scope,
                'Use the preferences path belonging to the selected scope.'
            );
        }
    }
    return success({
        defaultTarget: defaultTarget,
        defaultPreferences: defaultPreferences,
        preferencesFile: preferencesFile
    });
}

function resolveTarget(options) {
    const settings = options || {};
    const readValue = settings.readKeyValue || (
        (file, key) => readKeyValue(file, key, settings.fileSystem)
    );
    const normalizePath = settings.normalizePath || (value => value);
    let targetPath = settings.targetPath || '';
    if (!settings.targetExplicit && settings.preferencesFile) {
        const configuredTarget = readValue(
            settings.preferencesFile,
            'modding_api_reference_path'
        );
        if (configuredTarget) {
            targetPath = configuredTarget;
        }
    }
    if (!targetPath) {
        if (settings.defaultTarget) {
            targetPath = settings.defaultTarget;
        }
        else {
            return failure(
                2,
                'no local reference path was provided',
                'Use --target-path, --scope, or configure modding_api_reference_path in preferences.md.'
            );
        }
    }
    targetPath = normalizePath(targetPath);
    return success({
        targetPath: targetPath,
        lockFile: targetPath + '.lock'
    });
}

function resolveSelector(options) {
    const settings = options || {};
    const readValue = settings.readKeyValue || (
        (file, key) => readKeyValue(file, key, settings.fileSystem)
    );
    let selector = settings.selector || '';
    if (!settings.selectorExplicit) {
        const configuredSelector = readValue(
            settings.preferencesFile,
            'modding_api_reference_selector'
        );
        selector = configuredSelector || 'latest';
    }
    if (!selector) {
        return failure(
            2,
            'no selector was configured',
            'Use --selector or add modding_api_reference_selector to preferences.md.'
        );
    }
    const parsed = parseSelector(selector, settings.parseSelectorOptions);
    if (!parsed.ok) {
        return parsed;
    }
    return success({
        selector: selector,
        selectorKind: parsed.selectorKind,
        resolvedRef: parsed.resolvedRef
    });
}

function inspectCheckout(options) {
    const settings = options || {};
    const io = settings.fileSystem || fs;
    const targetPath = settings.targetPath;
    const runGit = settings.runGit;
    if (
        !io.existsSync(targetPath) ||
        !io.statSync(targetPath).isDirectory()
    ) {
        return failure(
            2,
            'reference path does not exist: ' + targetPath,
            'Run the fresh clone command or provide the configured checkout path.',
            { worktreeState: 'missing', currentHead: '<unavailable>' }
        );
    }
    const inside = runGit(targetPath, ['rev-parse', '--is-inside-work-tree']);
    if (inside.code !== 0 || inside.output.trim() !== 'true') {
        return failure(
            1,
            'reference path is not a Git worktree: ' + targetPath,
            'Use a valid ModdingAPI checkout or clone a fresh reference into a missing path.',
            { worktreeState: 'invalid', currentHead: '<unavailable>' }
        );
    }
    const headResult = runGit(targetPath, ['rev-parse', 'HEAD']);
    const currentHead = headResult.code === 0
        ? headResult.output.trim().split(/\r?\n/)[0]
        : '<unavailable>';
    if (currentHead === '<unavailable>') {
        return failure(
            1,
            'reference worktree has no readable HEAD',
            'Repair the checkout manually or create a fresh reference in another path.',
            { worktreeState: 'invalid', currentHead: currentHead }
        );
    }
    const status = runGit(targetPath, [
        'status',
        '--porcelain',
        '--untracked-files=all'
    ]);
    if (status.code !== 0) {
        return failure(
            1,
            'could not inspect reference worktree state',
            'Inspect the checkout manually and retry.',
            { worktreeState: 'invalid', currentHead: currentHead }
        );
    }
    if (status.output.trim().length > 0) {
        return failure(
            1,
            'reference worktree contains local changes',
            'Commit or remove changes manually, then retry; the manager will not stash, reset, or delete them.',
            { worktreeState: 'dirty', currentHead: currentHead }
        );
    }
    const origin = runGit(targetPath, ['config', '--get', 'remote.origin.url']);
    if (origin.code !== 0 || !origin.output.trim()) {
        return failure(
            1,
            'reference checkout has no origin remote',
            'Add the official ModdingAPI origin manually or create a fresh reference.',
            { worktreeState: 'clean', currentHead: currentHead }
        );
    }
    if (
        canonicalRepository(origin.output.trim()) !==
        canonicalRepository(settings.repository || OFFICIAL_REPOSITORY)
    ) {
        return failure(
            1,
            'reference origin does not match the official ModdingAPI repository: ' + origin.output.trim(),
            'Do not use this checkout; configure the official upstream or create a fresh reference.',
            { worktreeState: 'clean', currentHead: currentHead }
        );
    }
    return success({
        currentHead: currentHead,
        worktreeState: 'clean',
        origin: origin.output.trim()
    });
}

function validateCheckoutShape(options) {
    const settings = options || {};
    const selectorKind = settings.selectorKind;
    const resolvedRef = settings.resolvedRef;
    const targetPath = settings.targetPath;
    const runGit = settings.runGit;
    if (selectorKind === 'branch') {
        const branch = runGit(targetPath, [
            'symbolic-ref',
            '--quiet',
            '--short',
            'HEAD'
        ]);
        const branchName = branch.code === 0 ? branch.output.trim() : '';
        if (branchName !== resolvedRef) {
            return failure(
                1,
                'current branch is ' + branchName + ', but selector requires branch ' + resolvedRef,
                'Check out the requested branch manually or use a fresh reference; the manager will not replace the current branch.'
            );
        }
        const upstream = runGit(targetPath, [
            'rev-parse',
            '--abbrev-ref',
            '--symbolic-full-name',
            '@{upstream}'
        ]);
        let upstreamName = upstream.code === 0 ? upstream.output.trim() : '';
        if (!upstreamName) {
            const configuredRemote = runGit(targetPath, [
                'config',
                '--get',
                'branch.' + resolvedRef + '.remote'
            ]);
            const configuredMerge = runGit(targetPath, [
                'config',
                '--get',
                'branch.' + resolvedRef + '.merge'
            ]);
            if (
                configuredRemote.code === 0 &&
                configuredRemote.output.trim() === 'origin' &&
                configuredMerge.code === 0 &&
                configuredMerge.output.trim() === 'refs/heads/' + resolvedRef
            ) {
                upstreamName = 'origin/' + resolvedRef;
            }
        }
        if (upstreamName !== 'origin/' + resolvedRef) {
            return failure(
                1,
                settings.branchTrackingCause || 'current branch does not track origin/' + resolvedRef,
                settings.branchTrackingNextStep || 'Repair the tracking configuration manually or create a fresh reference; the manager will not rewrite it.'
            );
        }
        return success();
    }
    if (
        selectorKind === 'release' ||
        selectorKind === 'tag' ||
        selectorKind === 'commit'
    ) {
        const headReference = runGit(targetPath, [
            'symbolic-ref',
            '--quiet',
            '--short',
            'HEAD'
        ]);
        if (headReference.code === 0) {
            return failure(
                1,
                settings.fixedDetachedCause || 'fixed selector requires detached HEAD',
                settings.fixedDetachedNextStep || 'Detach HEAD manually at the intended reference or create a fresh fixed-reference checkout.'
            );
        }
        return success();
    }
    return failure(
        1,
        'unsupported selector kind: ' + selectorKind,
        'Use latest, tag:REF, branch:REF, or commit:SHA.'
    );
}

function parseResolverMetadata(values) {
    const source = values || {};
    return {
        repository: source.MODDING_API_REPOSITORY || '',
        selectorKind: source.MODDING_API_SELECTOR_KIND || '',
        resolvedRef: source.MODDING_API_RESOLVED_REF || '',
        resolvedTag: source.MODDING_API_RESOLVED_TAG || '',
        resolvedCommit: source.MODDING_API_RESOLVED_COMMIT || ''
    };
}

function readLock(file, fileSystem) {
    return {
        selector: readKeyValue(file, 'selector', fileSystem),
        resolvedTag: readKeyValue(file, 'resolved_tag', fileSystem),
        resolvedCommit: readKeyValue(file, 'resolved_commit', fileSystem),
        checkedAt: readKeyValue(file, 'checked_at', fileSystem),
        repository: readKeyValue(file, 'repository', fileSystem),
        hasResolvedTag: hasKey(file, 'resolved_tag', fileSystem)
    };
}

function lockMatches(options) {
    const settings = options || {};
    const io = settings.fileSystem || fs;
    const lock = readLock(settings.lockFile, io);
    return Boolean(
        io.existsSync(settings.lockFile) &&
        lock.selector === settings.selector &&
        lock.hasResolvedTag &&
        lock.resolvedTag === settings.resolvedTag &&
        lock.resolvedCommit === settings.resolvedCommit &&
        (
            settings.selectorKind !== 'commit' ||
            settings.resolvedCommit.toLowerCase() === settings.resolvedRef.toLowerCase()
        ) &&
        validCheckedAt(lock.checkedAt) &&
        canonicalRepository(lock.repository) ===
            canonicalRepository(settings.repository || OFFICIAL_REPOSITORY)
    );
}

function validateLock(options) {
    const settings = options || {};
    const io = settings.fileSystem || fs;
    const lock = readLock(settings.lockFile, io);
    if (!io.existsSync(settings.lockFile)) {
        return failure(
            1,
            'offline validation requires the sibling lock state: ' + settings.lockFile,
            'Run an online check or update once, then retry offline.'
        );
    }
    if (
        !lock.selector ||
        !lock.hasResolvedTag ||
        !lock.resolvedCommit ||
        !lock.checkedAt
    ) {
        return failure(
            1,
            'lock state is incomplete: ' + settings.lockFile,
            'Run an online check to rebuild the lock state after inspecting the checkout.'
        );
    }
    if (!validCheckedAt(lock.checkedAt)) {
        return failure(
            1,
            'lock state contains an invalid checked_at value',
            'Run an online check to rebuild the lock state.'
        );
    }
    if (lock.selector !== settings.selector) {
        return failure(
            1,
            'lock selector ' + lock.selector + ' does not match requested selector ' + settings.selector,
            'Use the locked selector, run an online update for the requested selector, or inspect the lock manually.'
        );
    }
    if (!/^[0-9a-fA-F]{40}$/.test(lock.resolvedCommit)) {
        return failure(
            1,
            'lock state contains an invalid resolved commit',
            'Run an online check to rebuild the lock state.'
        );
    }
    if (
        settings.selectorKind === 'commit' &&
        lock.resolvedCommit.toLowerCase() !== settings.resolvedRef.toLowerCase()
    ) {
        return failure(
            1,
            'lock commit does not match the commit selector ' + settings.selector,
            'Run an online check for the requested commit or inspect the lock manually.'
        );
    }
    if (
        lock.repository &&
        canonicalRepository(lock.repository) !==
            canonicalRepository(settings.repository || OFFICIAL_REPOSITORY)
    ) {
        return failure(
            1,
            'lock state repository does not match the official ModdingAPI repository',
            'Run an online check after correcting the lock state or create a fresh reference.'
        );
    }
    if (settings.selector === 'latest' && !lock.resolvedTag) {
        return failure(
            1,
            'latest lock state has no resolved tag',
            'Run an online check to rebuild the lock state.'
        );
    }
    if (
        settings.selector.startsWith('tag:') &&
        lock.resolvedTag !== settings.selector.slice(4)
    ) {
        return failure(
            1,
            'lock tag ' + lock.resolvedTag + ' does not match requested selector ' + settings.selector,
            'Run an online update for the requested tag or inspect the lock manually.'
        );
    }
    return success({
        resolvedTag: lock.resolvedTag,
        resolvedCommit: lock.resolvedCommit,
        checkedAt: lock.checkedAt
    });
}

module.exports = {
    OFFICIAL_REPOSITORY,
    canonicalRepository,
    failure,
    hasKey,
    inspectCheckout,
    lockMatches,
    parseResolverMetadata,
    parseSelector,
    readKeyValue,
    readLock,
    resolveSelector,
    resolveTarget,
    selectPreferenceContext,
    success,
    text,
    validateCheckoutShape,
    validateLock,
    validCheckedAt
};
