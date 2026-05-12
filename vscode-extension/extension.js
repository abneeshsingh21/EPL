// EPL VS Code Extension — LSP Client + Run Commands
// Connects VS Code to EPL's Language Server for diagnostics, completions, and hover.

const vscode = require('vscode');

let client;

function getActiveEPLFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'epl') {
        vscode.window.showWarningMessage('Open an .epl file first');
        return null;
    }
    return editor.document.fileName;
}

function runCommandInTerminal(name, command) {
    // Reuse only terminals created with compatible shell semantics.
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

function activate(context) {
    const config = vscode.workspace.getConfiguration('epl');
    const eplPath = config.get('lsp.path', 'epl');
    const lspEnabled = config.get('lsp.enabled', true);
    const extensionVersion = context.extension?.packageJSON?.version || 'unknown';

    function runEplCommand(name, args) {
        runCommandInTerminal(name, buildEplCommand(eplPath, args));
    }

    // ── Register ALL commands FIRST (before LSP) ─────────
    // This ensures commands work even if LSP fails to start.

    const runCommand = vscode.commands.registerCommand('epl.run', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        runEplCommand('EPL', ['run', filePath]);
    });

    const checkCommand = vscode.commands.registerCommand('epl.check', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        const strict = config.get('strictMode', false);
        const args = strict ? ['check', filePath, '--strict'] : ['check', filePath];
        runEplCommand('EPL Check', args);
    });

    const formatCommand = vscode.commands.registerCommand('epl.format', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        runEplCommand('EPL Format', ['fmt', filePath, '--in-place']);
    });

    const compileFile = vscode.commands.registerCommand('epl.compileFile', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        runEplCommand('EPL Build', ['build', filePath]);
    });

    const lintFile = vscode.commands.registerCommand('epl.lintFile', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        runEplCommand('EPL Lint', ['lint', filePath]);
    });

    const profileFile = vscode.commands.registerCommand('epl.profileFile', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
        runEplCommand('EPL Profile', ['profile', filePath]);
    });

    const runFile = vscode.commands.registerCommand('epl.runFile', () => {
        vscode.commands.executeCommand('epl.run');
    });

    const fixFile = vscode.commands.registerCommand('epl.fixFile', () => {
        const filePath = getActiveEPLFile();
        if (!filePath) return;
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
        runEplCommand('EPL Deploy', ['deploy', target, filePath]);
    });

    const playgroundCommand = vscode.commands.registerCommand('epl.playground', () => {
        runEplCommand('EPL Playground', ['playground']);
    });

    const copilotCommand = vscode.commands.registerCommand('epl.copilot', () => {
        runEplCommand('EPL Copilot', ['copilot']);
    });

    const monitorCommand = vscode.commands.registerCommand('epl.monitor', async () => {
        const url = await vscode.window.showInputBox({
            prompt: 'Enter the URL to monitor',
            placeHolder: 'http://localhost:8000',
            value: 'http://localhost:8000'
        });
        if (!url) return;
        runEplCommand('EPL Monitor', ['monitor', url]);
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
        monitorCommand
    );

    // ── Status Bar ──────────────────────────────────────
    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBar.text = '$(zap) EPL';
    statusBar.tooltip = 'Click to run the current EPL file';
    statusBar.command = 'epl.run';
    statusBar.show();
    context.subscriptions.push(statusBar);

    // ── LSP Client (AFTER commands, safely wrapped) ─────
    if (lspEnabled) {
        try {
            const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

            const serverOptions = {
                command: eplPath,
                args: ['lsp'],
                transport: TransportKind.stdio
            };

            const clientOptions = {
                documentSelector: [{ scheme: 'file', language: 'epl' }],
                synchronize: {
                    fileEvents: vscode.workspace.createFileSystemWatcher('**/*.epl')
                }
            };

            client = new LanguageClient(
                'epl-lsp',
                'EPL Language Server',
                serverOptions,
                clientOptions
            );

            client.start().catch(err => {
                console.warn('EPL LSP server failed to start:', err.message);
                // Don't crash the extension — commands still work without LSP
            });

            context.subscriptions.push(client);
        } catch (err) {
            console.warn('EPL LSP client could not be initialized:', err.message);
            // Extension continues to work without LSP features
        }
    }

    console.log(`EPL extension v${extensionVersion} activated`);
}

function deactivate() {
    if (client) {
        return client.stop();
    }
}

module.exports = { activate, deactivate, buildEplCommand };
