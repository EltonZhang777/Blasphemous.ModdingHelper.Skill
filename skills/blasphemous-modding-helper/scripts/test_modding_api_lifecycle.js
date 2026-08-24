'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const lifecycle = require('./modding_api_lifecycle');

function fakeFileSystem(existingFiles) {
    const files = new Set(existingFiles);
    return {
        existsSync(file) {
            return files.has(file);
        },
        statSync() {
            return { isDirectory: () => true };
        }
    };
}

function gitMap(entries) {
    return (cwd, args) => {
        const key = cwd + '|' + args.join(' ');
        return entries[key] || { code: 1, output: '' };
    };
}

function run() {
    assert.deepStrictEqual(
        lifecycle.parseSelector('latest'),
        { ok: true, selector: 'latest', selectorKind: 'release', resolvedRef: '' },
    );
    assert.strictEqual(lifecycle.parseSelector('tag:v1.0.0').selectorKind, 'tag');
    assert.strictEqual(lifecycle.parseSelector('branch/main').ok, false);
    assert.strictEqual(
        lifecycle.parseSelector('commit:bad').cause,
        'commit selector must contain a 40-character SHA',
    );
    assert.strictEqual(
        lifecycle.canonicalRepository('git@github.com:BrandenEK/Blasphemous.ModdingAPI.git'),
        'https://github.com/brandenek/blasphemous.moddingapi',
    );

    const fixtureRoot = path.join(os.tmpdir(), 'modding-api-lifecycle-seam-test');
    const projectPreferences = path.join(
        fixtureRoot,
        'project',
        '.skills',
        'blasphemous-modding-helper',
        'preferences.md',
    );
    const userPreferences = path.join(
        fixtureRoot,
        'home',
        '.skills',
        'blasphemous-modding-helper',
        'preferences.md',
    );
    const projectContext = lifecycle.selectPreferenceContext({
        cwd: path.join(fixtureRoot, 'project'),
        home: path.join(fixtureRoot, 'home'),
        fileSystem: fakeFileSystem([projectPreferences, userPreferences]),
        targetExplicit: false,
        preferencesExplicit: false,
    });
    assert.strictEqual(projectContext.ok, true);
    assert.strictEqual(projectContext.preferencesFile, projectPreferences);

    const userContext = lifecycle.selectPreferenceContext({
        cwd: path.join(fixtureRoot, 'other-project'),
        home: path.join(fixtureRoot, 'home'),
        fileSystem: fakeFileSystem([userPreferences]),
        targetExplicit: false,
        preferencesExplicit: false,
    });
    assert.strictEqual(userContext.preferencesFile, userPreferences);

    const branchCheckout = lifecycle.validateCheckoutShape({
        targetPath: '/fixture/reference',
        selectorKind: 'branch',
        resolvedRef: 'main',
        runGit: gitMap({
            '/fixture/reference|symbolic-ref --quiet --short HEAD': { code: 0, output: 'main\n' },
            '/fixture/reference|rev-parse --abbrev-ref --symbolic-full-name @{upstream}': { code: 0, output: 'origin/main\n' }
        })
    });
    assert.strictEqual(branchCheckout.ok, true);

    const detachedCheckout = lifecycle.validateCheckoutShape({
        targetPath: '/fixture/reference',
        selectorKind: 'tag',
        resolvedRef: 'v1.0.0',
        runGit: gitMap({
            '/fixture/reference|symbolic-ref --quiet --short HEAD': { code: 1, output: '' }
        })
    });
    assert.strictEqual(detachedCheckout.ok, true);

    const lockRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'modding-api-lifecycle-lock-'));
    try {
        const lockFile = path.join(lockRoot, 'reference.lock');
        fs.writeFileSync(
            lockFile,
            [
                'selector: latest',
                'resolved_tag: v1.0.0',
                'resolved_commit: 0123456789012345678901234567890123456789',
                'checked_at: 2026-08-24T12:00:00Z',
                'repository: https://github.com/BrandenEK/Blasphemous.ModdingAPI.git',
                ''
            ].join('\n'),
            'utf8',
        );
        const lockOptions = {
            fileSystem: fs,
            lockFile,
            selector: 'latest',
            selectorKind: 'release',
            resolvedRef: '',
            resolvedTag: 'v1.0.0',
            resolvedCommit: '0123456789012345678901234567890123456789',
            repository: lifecycle.OFFICIAL_REPOSITORY
        };
        assert.strictEqual(lifecycle.lockMatches(lockOptions), true);
        assert.strictEqual(lifecycle.validateLock(lockOptions).ok, true);
        const mismatched = lifecycle.validateLock(Object.assign({}, lockOptions, {
            selector: 'tag:v1.0.0'
        }));
        assert.strictEqual(mismatched.ok, false);
        assert.match(mismatched.cause, /does not match requested selector/);
    }
    finally {
        fs.rmSync(lockRoot, { recursive: true, force: true });
    }

    process.stdout.write('[OK] modding_api_lifecycle semantic seams\n');
}

try {
    run();
}
catch (error) {
    process.stderr.write('[FAIL] ' + (error && error.stack ? error.stack : error) + '\n');
    process.exitCode = 1;
}
