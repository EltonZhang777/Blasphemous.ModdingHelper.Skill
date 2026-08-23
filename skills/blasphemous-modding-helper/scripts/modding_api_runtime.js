'use strict';

const childProcess = require('child_process');
const path = require('path');

function text(value) {
    return value === undefined || value === null ? '' : String(value);
}

function commandOutput(result) {
    const parts = [];
    if (result && result.error) {
        parts.push(text(result.error.message || result.error.code || result.error));
    }
    if (result) {
        parts.push(text(result.stdout), text(result.stderr));
    }
    return parts.filter(Boolean).join('\n');
}

function networkFailure(value) {
    return /network|curl|connect|resolve host|timed out|timeout|ETIMEDOUT|ECONNREFUSED|ECONNRESET|unable to access|could not resolve|failed to connect|connection refused|connection reset|http [45]\d\d/i.test(text(value));
}

function runGit(cwd, args) {
    const result = childProcess.spawnSync('git', ['-C', cwd].concat(args), {
        encoding: 'utf8',
        windowsHide: true
    });
    return {
        code: typeof result.status === 'number' ? result.status : 1,
        output: commandOutput(result)
    };
}

function runResolver(scriptDir, selector, metadataFile) {
    const resolverName = process.platform === 'win32' ? 'resolve_modding_api.ps1' : 'resolve_modding_api.sh';
    const resolverPath = path.join(scriptDir, resolverName);
    const args = process.platform === 'win32'
        ? ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', resolverPath, '-Selector', selector]
        : [resolverPath, '--selector', selector];
    if (metadataFile) {
        args.push(process.platform === 'win32' ? '-MetadataFile' : '--metadata-file', metadataFile);
    }
    const commands = process.platform === 'win32'
        ? [process.env.MODDING_API_POWERSHELL, 'powershell.exe', 'pwsh'].filter(Boolean)
        : ['bash'];
    const timeoutValue = Number(process.env.MODDING_API_RESOLVER_TIMEOUT_MS || 75000);
    const timeout = Number.isFinite(timeoutValue) && timeoutValue > 0 ? timeoutValue : 75000;
    for (const command of commands) {
        const result = childProcess.spawnSync(command, args, {
            encoding: 'utf8',
            timeout,
            windowsHide: true
        });
        if (!result.error || result.error.code !== 'ENOENT') {
            return {
                code: typeof result.status === 'number' ? result.status : 1,
                output: commandOutput(result)
            };
        }
    }
    return { code: 1, output: 'resolver runtime was not found' };
}

function resolverValues(output) {
    const values = {};
    for (const line of text(output).split(/\r?\n/)) {
        const separator = line.indexOf('=');
        if (separator > 0) {
            values[line.slice(0, separator)] = line.slice(separator + 1);
        }
    }
    return values;
}

module.exports = { commandOutput, networkFailure, runGit, runResolver, resolverValues };
