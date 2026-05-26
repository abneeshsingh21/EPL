// EPL VS Code Extension v2.1.0 — LSP Client + Run Commands
// Connects VS Code to EPL's Language Server for diagnostics, completions, and hover.

const vscode = require('vscode');

let client;
let outputChannel;
let statusBarItem;
let diagnosticStatusItem;

// ── Helpers ─────────────────────────────────────────────

function getActiveEPLFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'epl') {
        vscode.window.showWarningMessage('Open an .epl file first');
        return null;
    }
    return editor.document.fileName;
}

function runCommandInTerminal(name, command) {
    const existing = vscode.window.terminals.find(t => t.name === name && isReusableEplTerminal(t));
    const terminal = existing || createEplTerminal(name);
    terminal.sendText(command);
    terminal.show();
}

function isReusableEplTerminal(terminal) {
    if (process.platform !== 'win32') {
        return true;
    }
    const shellPath = terminal.creationOptions && terminal.creationOptions.shellPath;
    return typeof shellPath === 'string' && shellPath.toLowerCase().includes('powershell');
}

function createEplTerminal(name) {
    if (process.platform === 'win32') {
        return vscode.window.createTerminal({
            name,
            shellPath: 'powershell.exe',
            shellArgs: ['-NoLogo']
        });
    }
    return vscode.window.createTerminal(name);
}

function quoteForTerminal(value) {
    const text = String(value);
    if (process.platform === 'win32') {
        return `'${text.replace(/'/g, "''")}'`;
    }
    return `'${text.replace(/'/g, "'\\''")}'`;
}

function buildEplCommand(eplPath, args) {
    const executable = quoteForTerminal(eplPath || 'epl');
    const prefix = process.platform === 'win32' ? `& ${executable}` : executable;
    return [prefix, ...args.map(quoteForTerminal)].join(' ');
}

// ── Status Bar ──────────────────────────────────────────

function createStatusBar(context) {
    // Main EPL status
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.text = '$(zap) EPL';
    statusBarItem.tooltip = 'EPL — Click to run current file';
    statusBarItem.command = 'epl.run';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // Diagnostic count indicator
    diagnosticStatusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 99);
    diagnosticStatusItem.command = 'workbench.actions.view.problems';
    updateDiagnosticStatus();
    diagnosticStatusItem.show();
    context.subscriptions.push(diagnosticStatusItem);
}

function updateDiagnosticStatus() {
    if (!diagnosticStatusItem) return;

    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'epl') {
        diagnosticStatusItem.text = '';
        diagnosticStatusItem.hide();
        return;
    }

    const diagnostics = vscode.languages.getDiagnostics(editor.document.uri);
    let errors = 0;
    let warnings = 0;
    for (const d of diagnostics) {
        if (d.severity === vscode.DiagnosticSeverity.Error) errors++;
        else if (d.severity === vscode.DiagnosticSeverity.Warning) warnings++;
    }

    if (errors === 0 && warnings === 0) {
        diagnosticStatusItem.text = '$(check) 0 issues';
        diagnosticStatusItem.backgroundColor = undefined;
        diagnosticStatusItem.tooltip = 'No problems in this file';
    } else {
        const parts = [];
        if (errors > 0) parts.push(`$(error) ${errors}`);
        if (warnings > 0) parts.push(`$(warning) ${warnings}`);
        diagnosticStatusItem.text = parts.join('  ');
        diagnosticStatusItem.tooltip = `${errors} error(s), ${warnings} warning(s) — click to open Problems`;
        if (errors > 0) {
            diagnosticStatusItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
        } else {
            diagnosticStatusItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        }
    }
    diagnosticStatusItem.show();
}

// ── PyPI Update Checker ─────────────────────────────────

function checkForEplUpdate(eplPath, logFn) {
    const { exec } = require('child_process');
    const https = require('https');

    // Get installed version
    exec(`"${eplPath}" --version`, { timeout: 5000 }, (err, stdout) => {
        if (err) {
            logFn('Update check: Could not determine installed EPL version');
            return;
        }

        // Parse installed version from output like "EPL v7.6.0" or "7.6.0"
        const match = stdout.trim().match(/(\d+\.\d+\.\d+)/);
        if (!match) return;
        const installed = match[1];

        // Fetch latest from PyPI
        const req = https.get('https://pypi.org/pypi/eplang/json', { timeout: 5000 }, (res) => {
            let data = '';
            res.on('data', chunk => { data += chunk; });
            res.on('end', () => {
                try {
                    const info = JSON.parse(data);
                    const latest = info.info && info.info.version;
                    if (!latest) return;

                    // Compare versions
                    const toNum = v => v.split('.').map(Number);
                    const inst = toNum(installed);
                    const lat = toNum(latest);
                    const isNewer = lat[0] > inst[0] ||
                        (lat[0] === inst[0] && lat[1] > inst[1]) ||
                        (lat[0] === inst[0] && lat[1] === inst[1] && lat[2] > inst[2]);

                    if (isNewer) {
                        logFn(`Update available: v${installed} → v${latest}`);
                        vscode.window.showInformationMessage(
                            `EPL v${latest} is available (you have v${installed}).`,
                            'Update Now',
                            'Dismiss'
                        ).then(choice => {
                            if (choice === 'Update Now') {
                                const terminal = vscode.window.createTerminal('EPL Update');
                                terminal.sendText('pip install --upgrade eplang');
                                terminal.show();
                            }
                        });
                    } else {
                        logFn(`EPL is up to date (v${installed})`);
                    }
                } catch (e) {
                    logFn('Update check: Failed to parse PyPI response');
                }
            });
        });
        req.on('error', () => { logFn('Update check: Network request failed'); });
        req.end();
    });
}

// ── Activation ──────────────────────────────────────────

function activate(context) {
    const config = vscode.workspace.getConfiguration('epl');
    const eplPath = config.get('lsp.path', 'epl');
    const lspEnabled = config.get('lsp.enabled', true);
    const extensionVersion = context.extension?.packageJSON?.version || 'unknown';

    // ── Output Channel ──────────────────────────────────
    outputChannel = vscode.window.createOutputChannel('EPL', { log: true });
    outputChannel.appendLine(`EPL extension v${extensionVersion} activated`);
    outputChannel.appendLine(`Platform: ${process.platform}, LSP enabled: ${lspEnabled}`);
    context.subscriptions.push(outputChannel);

    function log(msg) {
        outputChannel.appendLine(`[${new Date().toLocaleTimeString()}] ${msg}`);
    }

    function runEplCommand(name, args) {
        runCommandInTerminal(name, buildEplCommand(eplPath, args));
    }

    // ── Register ALL commands FIRST (before LSP) ─────────
    const runCommand = vscode.commands.registerCommand('epl.run', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        log(`Run: ${filePath}`);
        runEplCommand('EPL', ['run', filePath]);
    });

    const checkCommand = vscode.commands.registerCommand('epl.check', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        const strict = config.get('strictMode', false);
        const args = strict ? ['check', filePath, '--strict'] : ['check', filePath];
        log(`Type check: ${filePath}`);
        runEplCommand('EPL Check', args);
    });

    const formatCommand = vscode.commands.registerCommand('epl.format', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        log(`Format: ${filePath}`);
        runEplCommand('EPL Format', ['fmt', filePath, '--in-place']);
    });

    const compileFile = vscode.commands.registerCommand('epl.compileFile', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        log(`Build: ${filePath}`);
        runEplCommand('EPL Build', ['build', filePath]);
    });

    const lintFile = vscode.commands.registerCommand('epl.lintFile', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        log(`Lint: ${filePath}`);
        runEplCommand('EPL Lint', ['lint', filePath]);
    });

    const profileFile = vscode.commands.registerCommand('epl.profileFile', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        log(`Profile: ${filePath}`);
        runEplCommand('EPL Profile', ['profile', filePath]);
    });

    const runFile = vscode.commands.registerCommand('epl.runFile', () => {
        vscode.commands.executeCommand('epl.run');
    });

    const fixFile = vscode.commands.registerCommand('epl.fixFile', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        log(`AI Fix: ${filePath}`);
        runEplCommand('EPL AI Explainer', ['fix', filePath]);
    });

    const formatFile = vscode.commands.registerCommand('epl.formatFile', () => {
        vscode.commands.executeCommand('epl.format');
    });

    const serveCommand = vscode.commands.registerCommand('epl.serve', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        const port = config.get('serve.port', 8000);
        const obs = config.get('serve.observability', false);
        const args = ['serve', filePath, '--port', String(port)];
        if (obs) args.push('--observability');
        log(`Serve: ${filePath} on port ${port}`);
        runEplCommand('EPL Server', args);
    });

    const deployCommand = vscode.commands.registerCommand('epl.deploy', async () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        const target = await vscode.window.showQuickPick(
            ['k8s', 'aws', 'gcp', 'azure', 'docker'],
            { placeHolder: 'Select deployment target' }
        );
        if (!target) return;
        log(`Deploy: ${filePath} → ${target}`);
        runEplCommand('EPL Deploy', ['deploy', target, filePath]);
    });

    const playgroundCommand = vscode.commands.registerCommand('epl.playground', () => {
        log('Starting playground');
        runEplCommand('EPL Playground', ['playground']);
    });

    const copilotCommand = vscode.commands.registerCommand('epl.copilot', () => {
        log('Starting AI Copilot');
        runEplCommand('EPL Copilot', ['copilot']);
    });

    const monitorCommand = vscode.commands.registerCommand('epl.monitor', async () => {
        const url = await vscode.window.showInputBox({
            prompt: 'Enter the URL to monitor',
            placeHolder: 'http://localhost:8000',
            value: 'http://localhost:8000'
        });
        if (!url) return;
        log(`Monitor: ${url}`);
        runEplCommand('EPL Monitor', ['monitor', url]);
    });

    const watchCommand = vscode.commands.registerCommand('epl.watch', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        log(`Watch: ${filePath}`);
        runEplCommand('EPL Watch', ['watch', filePath, '--clear']);
    });

    const doctorCommand = vscode.commands.registerCommand('epl.doctor', () => {
        log('Running epl doctor...');
        runEplCommand('EPL Doctor', ['doctor']);
    });

    context.subscriptions.push(
        runCommand,
        checkCommand,
        formatCommand,
        runFile,
        compileFile,
        formatFile,
        lintFile,
        profileFile,
        fixFile,
        serveCommand,
        deployCommand,
        playgroundCommand,
        copilotCommand,
        monitorCommand,
        watchCommand,
        doctorCommand
    );

    // ── Status Bar ──────────────────────────────────────
    createStatusBar(context);

    // Update diagnostics status on editor change and diagnostic updates
    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(() => updateDiagnosticStatus()),
        vscode.languages.onDidChangeDiagnostics(() => updateDiagnosticStatus())
    );

    // ── LSP Client (AFTER commands, safely wrapped) ─────
    if (lspEnabled) {
        try {
            const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

            statusBarItem.text = '$(sync~spin) EPL';
            statusBarItem.tooltip = 'EPL Language Server starting...';
            log(`LSP: Starting server at "${eplPath} lsp"`);

            const serverOptions = {
                command: eplPath,
                args: ['lsp'],
                transport: TransportKind.stdio
            };

            const clientOptions = {
                documentSelector: [{ scheme: 'file', language: 'epl' }],
                synchronize: {
                    fileEvents: vscode.workspace.createFileSystemWatcher('**/*.epl')
                },
                outputChannel: outputChannel
            };

            client = new LanguageClient(
                'epl-lsp',
                'EPL Language Server',
                serverOptions,
                clientOptions
            );

            client.start().then(() => {
                statusBarItem.text = '$(zap) EPL';
                statusBarItem.tooltip = `EPL v${extensionVersion} — Language Server active`;
                log('LSP: Server started successfully');
            }).catch(err => {
                statusBarItem.text = '$(warning) EPL';
                statusBarItem.tooltip = 'EPL — Language Server failed to start';
                log(`LSP: Failed to start — ${err.message}`);
                // Don't crash the extension — commands still work without LSP
            });

            context.subscriptions.push(client);
        } catch (err) {
            statusBarItem.text = '$(warning) EPL';
            log(`LSP: Client initialization failed — ${err.message}`);
        }
    } else {
        statusBarItem.tooltip = `EPL v${extensionVersion} — Language Server disabled`;
        log('LSP: Disabled by user setting');
    }

    // ── Background Update Check ──────────────────────
    checkForEplUpdate(eplPath, log);

    log('Extension ready');
}

function deactivate() {
    if (outputChannel) {
        outputChannel.appendLine('EPL extension deactivated');
    }
    if (client) {
        return client.stop();
    }
}

module.exports = { activate, deactivate, buildEplCommand };
