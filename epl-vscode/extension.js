// EPL Language Extension for VS Code
// Provides: syntax highlighting, LSP integration, run/compile commands
const vscode = require('vscode');
const { spawn } = require('child_process');
const path = require('path');
const net = require('net');

let lspProcess = null;
let outputChannel = null;

function activate(context) {
    outputChannel = vscode.window.createOutputChannel('EPL');
    outputChannel.appendLine('EPL Extension activated (v5.0.0)');

    // ─── LSP Client (stdio transport) ───────────────────────
    const config = vscode.workspace.getConfiguration('epl');
    if (config.get('lsp.enabled', true)) {
        startLanguageServer(context);
    }

    // ─── Commands ───────────────────────────────────────────
    context.subscriptions.push(
        vscode.commands.registerCommand('epl.runFile', () => runEPLFile()),
        vscode.commands.registerCommand('epl.compileFile', () => compileEPLFile()),
        vscode.commands.registerCommand('epl.transpileJS', () => transpileFile('js')),
        vscode.commands.registerCommand('epl.transpileKotlin', () => transpileFile('kotlin')),
        vscode.commands.registerCommand('epl.generateAndroid', () => generateAndroidProject()),
        vscode.commands.registerCommand('epl.startWebServer', () => startWebServer()),
        vscode.commands.registerCommand('epl.restartServer', () => restartLanguageServer(context)),
        vscode.commands.registerCommand('epl.formatFile', () => formatEPLFile()),
        vscode.commands.registerCommand('epl.lintFile', () => lintEPLFile()),
        vscode.commands.registerCommand('epl.profileFile', () => profileEPLFile())
    );

    // ─── Status Bar ─────────────────────────────────────────
    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBar.text = '$(play) EPL';
    statusBar.command = 'epl.runFile';
    statusBar.tooltip = 'Run EPL File (Ctrl+Shift+R)';
    context.subscriptions.push(statusBar);

    // Show status bar only for .epl files
    vscode.window.onDidChangeActiveTextEditor((editor) => {
        if (editor && editor.document.languageId === 'epl') {
            statusBar.show();
        } else {
            statusBar.hide();
        }
    });

    if (vscode.window.activeTextEditor &&
        vscode.window.activeTextEditor.document.languageId === 'epl') {
        statusBar.show();
    }
}

// ─── Language Server ─────────────────────────────────────────
function startLanguageServer(context) {
    const config = vscode.workspace.getConfiguration('epl');
    const pythonPath = config.get('pythonPath', 'python');

    // Find the EPL LSP server module
    const eplRoot = findEPLRoot();
    if (!eplRoot) {
        outputChannel.appendLine('Warning: Could not find EPL installation. LSP features disabled.');
        return;
    }

    const lspModule = path.join(eplRoot, 'epl', 'lsp_server.py');

    outputChannel.appendLine(`Starting EPL Language Server: ${pythonPath} ${lspModule}`);

    lspProcess = spawn(pythonPath, [lspModule], {
        cwd: eplRoot,
        stdio: ['pipe', 'pipe', 'pipe']
    });

    const diagnosticCollection = vscode.languages.createDiagnosticCollection('epl');
    context.subscriptions.push(diagnosticCollection);

    let buffer = '';

    lspProcess.stdout.on('data', (data) => {
        buffer += data.toString();
        processLSPMessages(buffer, diagnosticCollection);
        // Keep unprocessed data
        const lastHeader = buffer.lastIndexOf('Content-Length:');
        if (lastHeader > 0) {
            const beforeHeader = buffer.substring(0, lastHeader);
            if (beforeHeader.includes('\r\n\r\n')) {
                buffer = buffer.substring(lastHeader);
            }
        }
    });

    lspProcess.stderr.on('data', (data) => {
        const msg = data.toString();
        if (config.get('trace.server', 'off') !== 'off') {
            outputChannel.appendLine(`[LSP stderr] ${msg}`);
        }
    });

    lspProcess.on('error', (err) => {
        outputChannel.appendLine(`LSP server error: ${err.message}`);
        vscode.window.showWarningMessage(
            `EPL Language Server failed to start. Ensure Python is installed. Error: ${err.message}`
        );
    });

    lspProcess.on('exit', (code) => {
        outputChannel.appendLine(`LSP server exited with code ${code}`);
    });

    // ─── Send LSP initialize ─────────────────────────────
    const initParams = {
        processId: process.pid,
        rootUri: vscode.workspace.workspaceFolders
            ? vscode.workspace.workspaceFolders[0].uri.toString()
            : null,
        capabilities: {
            textDocument: {
                synchronization: { dynamicRegistration: true },
                completion: { completionItem: { snippetSupport: true } },
                hover: { contentFormat: ['markdown', 'plaintext'] },
                definition: {},
                documentSymbol: {},
                formatting: {}
            }
        }
    };

    sendLSPRequest(0, 'initialize', initParams);

    // Send didOpen for active document
    if (vscode.window.activeTextEditor &&
        vscode.window.activeTextEditor.document.languageId === 'epl') {
        sendDidOpen(vscode.window.activeTextEditor.document);
    }

    // Track document changes
    context.subscriptions.push(
        vscode.workspace.onDidOpenTextDocument((doc) => {
            if (doc.languageId === 'epl') sendDidOpen(doc);
        }),
        vscode.workspace.onDidChangeTextDocument((event) => {
            if (event.document.languageId === 'epl') sendDidChange(event);
        }),
        vscode.workspace.onDidCloseTextDocument((doc) => {
            if (doc.languageId === 'epl') sendDidClose(doc);
            diagnosticCollection.delete(doc.uri);
        })
    );
}

function sendLSPRequest(id, method, params) {
    if (!lspProcess || lspProcess.killed) return;
    const msg = JSON.stringify({ jsonrpc: '2.0', id, method, params });
    const header = `Content-Length: ${Buffer.byteLength(msg)}\r\n\r\n`;
    try {
        lspProcess.stdin.write(header + msg);
    } catch (e) { /* ignore write errors on dead process */ }
}

function sendLSPNotification(method, params) {
    if (!lspProcess || lspProcess.killed) return;
    const msg = JSON.stringify({ jsonrpc: '2.0', method, params });
    const header = `Content-Length: ${Buffer.byteLength(msg)}\r\n\r\n`;
    try {
        lspProcess.stdin.write(header + msg);
    } catch (e) { /* ignore */ }
}

function sendDidOpen(doc) {
    sendLSPNotification('textDocument/didOpen', {
        textDocument: {
            uri: doc.uri.toString(),
            languageId: 'epl',
            version: doc.version,
            text: doc.getText()
        }
    });
}

function sendDidChange(event) {
    sendLSPNotification('textDocument/didChange', {
        textDocument: {
            uri: event.document.uri.toString(),
            version: event.document.version
        },
        contentChanges: [{ text: event.document.getText() }]
    });
}

function sendDidClose(doc) {
    sendLSPNotification('textDocument/didClose', {
        textDocument: { uri: doc.uri.toString() }
    });
}

function processLSPMessages(data, diagnostics) {
    // Parse JSON-RPC messages from LSP server
    try {
        const match = data.match(/Content-Length:\s*(\d+)\r?\n\r?\n([\s\S]*)/);
        if (!match) return;
        const len = parseInt(match[1]);
        const body = match[2];
        if (body.length < len) return; // incomplete
        const msg = JSON.parse(body.substring(0, len));

        if (msg.method === 'textDocument/publishDiagnostics') {
            const uri = vscode.Uri.parse(msg.params.uri);
            const diags = (msg.params.diagnostics || []).map(d => {
                const range = new vscode.Range(
                    d.range.start.line, d.range.start.character,
                    d.range.end.line, d.range.end.character
                );
                const severity = d.severity === 1
                    ? vscode.DiagnosticSeverity.Error
                    : d.severity === 2
                        ? vscode.DiagnosticSeverity.Warning
                        : vscode.DiagnosticSeverity.Information;
                return new vscode.Diagnostic(range, d.message, severity);
            });
            diagnostics.set(uri, diags);
        }
    } catch (e) { /* ignore parse errors */ }
}

// ─── Command Handlers ────────────────────────────────────────
function runEPLFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'epl') {
        vscode.window.showWarningMessage('Open an .epl file to run it.');
        return;
    }
    editor.document.save().then(() => {
        const filePath = editor.document.fileName;
        const terminal = vscode.window.createTerminal('EPL Run');
        terminal.show();
        terminal.sendText(`python -m epl "${filePath}"`);
    });
}

function compileEPLFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'epl') {
        vscode.window.showWarningMessage('Open an .epl file to compile it.');
        return;
    }
    editor.document.save().then(() => {
        const filePath = editor.document.fileName;
        const terminal = vscode.window.createTerminal('EPL Compile');
        terminal.show();
        terminal.sendText(`python -m epl compile "${filePath}"`);
    });
}

function transpileFile(target) {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'epl') {
        vscode.window.showWarningMessage('Open an .epl file to transpile.');
        return;
    }
    editor.document.save().then(() => {
        const filePath = editor.document.fileName;
        const terminal = vscode.window.createTerminal(`EPL ${target}`);
        terminal.show();
        terminal.sendText(`python -m epl ${target} "${filePath}"`);
    });
}

function generateAndroidProject() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'epl') {
        vscode.window.showWarningMessage('Open an .epl file to generate Android project.');
        return;
    }
    editor.document.save().then(() => {
        const filePath = editor.document.fileName;
        const outputDir = path.join(path.dirname(filePath), 'android_project');
        const terminal = vscode.window.createTerminal('EPL Android');
        terminal.show();
        terminal.sendText(`python -m epl android "${filePath}" --output "${outputDir}"`);
    });
}

function startWebServer() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'epl') {
        vscode.window.showWarningMessage('Open an .epl webapp file to start the server.');
        return;
    }
    editor.document.save().then(() => {
        const filePath = editor.document.fileName;
        const terminal = vscode.window.createTerminal('EPL Web Server');
        terminal.show();
        terminal.sendText(`python main.py serve "${filePath}"`);
    });
}

function restartLanguageServer(context) {
    if (lspProcess && !lspProcess.killed) {
        lspProcess.kill();
    }
    startLanguageServer(context);
    vscode.window.showInformationMessage('EPL Language Server restarted.');
}

function findEPLRoot() {
    // Try to find EPL installation
    // 1. Check if epl is in node_modules (unlikely)
    // 2. Check common install paths
    // 3. Check workspace
    const workspaceFolder = vscode.workspace.workspaceFolders
        ? vscode.workspace.workspaceFolders[0].uri.fsPath
        : null;

    if (workspaceFolder) {
        const localEpl = path.join(workspaceFolder, 'epl', 'lsp_server.py');
        const fs = require('fs');
        if (fs.existsSync(localEpl)) {
            return workspaceFolder;
        }
    }

    // Check if EPL is installed as a Python module
    return null; // Will try to use python -m epl.lsp_server
}

function deactivate() {
    if (lspProcess && !lspProcess.killed) {
        lspProcess.kill();
    }
    if (outputChannel) {
        outputChannel.dispose();
    }
}

function formatEPLFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'epl') {
        vscode.window.showErrorMessage('No EPL file is open.');
        return;
    }
    const filePath = editor.document.uri.fsPath;
    const config = vscode.workspace.getConfiguration('epl');
    const pythonPath = config.get('pythonPath', 'python');
    const terminal = vscode.window.createTerminal('EPL Format');
    terminal.sendText(`${pythonPath} -c "import sys; sys.path.insert(0,'.'); from main import *" 2>nul & ${pythonPath} main.py fmt "${filePath}" --in-place`);
    terminal.show();
}

function lintEPLFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'epl') {
        vscode.window.showErrorMessage('No EPL file is open.');
        return;
    }
    const filePath = editor.document.uri.fsPath;
    const config = vscode.workspace.getConfiguration('epl');
    const pythonPath = config.get('pythonPath', 'python');
    const terminal = vscode.window.createTerminal('EPL Lint');
    terminal.sendText(`${pythonPath} main.py lint "${filePath}"`);
    terminal.show();
}

function profileEPLFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'epl') {
        vscode.window.showErrorMessage('No EPL file is open.');
        return;
    }
    const filePath = editor.document.uri.fsPath;
    const config = vscode.workspace.getConfiguration('epl');
    const pythonPath = config.get('pythonPath', 'python');
    const terminal = vscode.window.createTerminal('EPL Profile');
    terminal.sendText(`${pythonPath} main.py profile "${filePath}"`);
    terminal.show();
}

module.exports = { activate, deactivate };
