'use strict';

const childProcess = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

function text(value) {
    return value === undefined || value === null ? '' : String(value);
}

function expandHome(value) {
    const home = process.env.HOME || process.env.USERPROFILE || os.homedir();
    if (value === '~') {
        return home;
    }
    if (value.startsWith('~/' ) || value.startsWith('~' + path.sep)) {
        return path.join(home, value.slice(2));
    }
    return value;
}

function normalizePath(value) {
    let expanded = expandHome(value);
    if (process.platform === 'win32') {
        const windowsDrive = expanded.match(/^\/(?:mnt\/)?([A-Za-z])(?:\/(.*))?$/);
        if (windowsDrive) {
            expanded = windowsDrive[1].toUpperCase() + ':\\' + text(windowsDrive[2]).replace(/\//g, '\\');
        }
        else if (process.env.MSYSTEM && expanded.startsWith('/')) {
            const converted = childProcess.spawnSync('cygpath', ['-w', expanded], { encoding: 'utf8', windowsHide: true });
            if (converted.status === 0 && text(converted.stdout).trim()) {
                expanded = text(converted.stdout).trim();
            }
        }
    }
    return path.resolve(expanded);
}

function replaceLockFile(temporary, file) {
    if (process.platform === 'win32') {
        const quotePowerShell = value => "'" + value.replace(/'/g, "''") + "'";
        const command =
            '$source=' + quotePowerShell(temporary) + ';' +
            '$destination=' + quotePowerShell(file) + ';' +
            'if (Test-Path -LiteralPath $destination) {' +
            '[System.IO.File]::Replace($source,$destination,$null,$true)' +
            '} else {' +
            '[System.IO.File]::Move($source,$destination)' +
            '}';
        const powershell = process.env.MODDING_API_POWERSHELL || 'powershell.exe';
        const result = childProcess.spawnSync(powershell, [
            '-NoProfile',
            '-NonInteractive',
            '-ExecutionPolicy',
            'Bypass',
            '-Command',
            command
        ], { encoding: 'utf8', windowsHide: true });
        if (!result.error && result.status === 0) {
            return;
        }
        throw new Error('atomic lock replacement is unavailable on this Windows host');
    }
    throw new Error('atomic lock replacement failed');
}

function writeLockState(file, selector, tag, commit, repository, checkedAt) {
    const content =
        'selector: ' + selector + '\n' +
        'resolved_tag: ' + tag + '\n' +
        'resolved_commit: ' + commit + '\n' +
        'checked_at: ' + checkedAt + '\n' +
        'repository: ' + repository + '\n';
    atomicWriteFile(file, content);
}

function atomicWriteFile(file, content) {
    const parent = path.dirname(file);
    if (!fs.existsSync(parent)) {
        throw new Error('write parent does not exist: ' + parent);
    }
    const temporary = path.join(
        parent,
        '.' + path.basename(file) + '.' + Math.random().toString(16).slice(2) + '.tmp'
    );
    try {
        fs.writeFileSync(temporary, content, 'utf8');
        try {
            fs.renameSync(temporary, file);
        }
        catch (error) {
            if (error.code !== 'EEXIST' && error.code !== 'EPERM' && error.code !== 'ENOTEMPTY') {
                throw error;
            }
            replaceLockFile(temporary, file);
        }
    }
    finally {
        if (fs.existsSync(temporary)) {
            fs.rmSync(temporary, { force: true });
        }
    }
}

function utcNow() {
    return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function usage() {
    process.stdout.write(
        'Usage:\n' +
        '  modding_api_lock.js --path PATH --selector SELECTOR --resolved-tag TAG --resolved-commit SHA --checked-at TIME --repository URL\n'
    );
}

function parseArgs(argv) {
    const values = {};
    for (let index = 0; index < argv.length; index += 1) {
        const key = argv[index];
        if (key === '--help') {
            usage();
            return null;
        }
        if (!key.startsWith('--') || index + 1 >= argv.length) {
            throw new Error('invalid lock writer arguments');
        }
        values[key.slice(2)] = argv[++index];
    }
    return values;
}

function run(argv) {
    const values = parseArgs(argv);
    if (values === null) {
        return 0;
    }
    const required = ['path', 'selector', 'resolved-commit', 'checked-at', 'repository'];
    for (const key of required) {
        if (!values[key]) {
            process.stderr.write('missing required lock writer argument: --' + key + '\n');
            return 2;
        }
    }
    if (!/^[0-9a-fA-F]{40}$/.test(values['resolved-commit'])) {
        process.stderr.write('resolved commit must be a 40-character SHA\n');
        return 2;
    }
    try {
        writeLockState(
            normalizePath(values.path),
            values.selector,
            text(values['resolved-tag']),
            values['resolved-commit'],
            values.repository,
            values['checked-at']
        );
    }
    catch (error) {
        process.stderr.write(text(error && error.message ? error.message : error) + '\n');
        return 1;
    }
    process.stdout.write('MODDING_API_LOCK_PATH=' + normalizePath(values.path) + '\n');
    process.stdout.write('MODDING_API_CHECKED_AT=' + values['checked-at'] + '\n');
    return 0;
}

module.exports = { writeLockState, atomicWriteFile, utcNow, normalizePath };

if (require.main === module) {
    try {
        process.exitCode = run(process.argv.slice(2));
    }
    catch (error) {
        process.stderr.write(text(error && error.message ? error.message : error) + '\n');
        process.exitCode = 2;
    }
}
