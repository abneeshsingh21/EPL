// EPL VS Code Extension — LSP Client
// Connects VS Code to EPL's Language Server for diagnostics, completions, and hover.

const vscode = require('vscode');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

let client;

function activate(context) {
    const config = vscode.workspace.getConfiguration('epl');
    const eplPath = config.get('lsp.path', 'epl');
    const lspEnabled = config.get('lsp.enabled', true);

    // ── LSP Client ──────────────────────────────────
    if (lspEnabled) {
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

        client.start();
        context.subscriptions.push(client);
    }

    // ── Run Command ─────────────────────────────────
    const runCommand = vscode.commands.registerCommand('epl.run', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.document.languageId !== 'epl') {
            vscode.window.showWarningMessage('Open an .epl file first');
            return;
        }

        const filePath = editor.document.fileName;
        const terminal = vscode.window.createTerminal('EPL');
        terminal.sendText(`${eplPath} run "${filePath}"`);
        terminal.show();
    });

    // ── Type Check Command ──────────────────────────
    const checkCommand = vscode.commands.registerCommand('epl.check', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.document.languageId !== 'epl') {
            vscode.window.showWarningMessage('Open an .epl file first');
            return;
        }

        const filePath = editor.document.fileName;
        const strict = config.get('strictMode', false);
        const flags = strict ? ' --strict' : '';
        const terminal = vscode.window.createTerminal('EPL Check');
        terminal.sendText(`${eplPath} check "${filePath}"${flags}`);
        terminal.show();
    });

    // ── Format Command ──────────────────────────────
    const formatCommand = vscode.commands.registerCommand('epl.format', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.document.languageId !== 'epl') {
            vscode.window.showWarningMessage('Open an .epl file first');
            return;
        }

        const filePath = editor.document.fileName;
        const terminal = vscode.window.createTerminal('EPL Format');
        terminal.sendText(`${eplPath} fmt "${filePath}"`);
        terminal.show();
    });

    context.subscriptions.push(runCommand, checkCommand, formatCommand);

    // ── Status Bar ──────────────────────────────────
    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBar.text = '$(zap) EPL';
    statusBar.tooltip = 'EPL Language Server active';
    statusBar.command = 'epl.run';
    statusBar.show();
    context.subscriptions.push(statusBar);

    console.log('EPL extension activated');
}

function deactivate() {
    if (client) {
        return client.stop();
    }
}

module.exports = { activate, deactivate };
