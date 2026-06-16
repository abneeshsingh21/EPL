import io
import time

from epl.lsp_server import JSONRPC, EPLLanguageServer


def _server(*, debounce=0.0, timeout=1.0):
    return EPLLanguageServer(
        JSONRPC(reader=io.BytesIO(b''), writer=io.BytesIO()),
        change_debounce_seconds=debounce,
        analysis_timeout_seconds=timeout,
    )


def test_lsp_did_change_is_debounced(monkeypatch):
    # Use a long debounce so NO timer fires during the rapid-change loop, then
    # flush once explicitly. This proves debouncing structurally (5 changes →
    # 1 analysis of the final text) without a sleep race — a short debounce
    # flakes on loaded CI runners where loop iterations outlast the window.
    uri = 'file:///rapid.epl'
    server = _server(debounce=60.0)
    calls = {'count': 0}
    original = server.analyzer.analyze_text

    def wrapped(text):
        calls['count'] += 1
        return original(text)

    monkeypatch.setattr(server.analyzer, 'analyze_text', wrapped)

    for index in range(5):
        server._on_did_change(
            {
                'textDocument': {'uri': uri},
                'contentChanges': [{'text': f'Print {index}'}],
            }
        )

    # No analysis should have run yet — all 5 changes are still pending.
    assert calls['count'] == 0
    assert server.analyzer.documents[uri] == 'Print 4'

    # Flush the single pending update; exactly one analysis of the latest text.
    server._flush_document_update(uri)
    assert calls['count'] == 1
    assert server.analyzer.documents[uri] == 'Print 4'


def test_lsp_completion_flushes_pending_update():
    server = _server(debounce=60.0)
    uri = 'file:///symbols.epl'
    server._on_did_change(
        {
            'textDocument': {'uri': uri},
            'contentChanges': [
                {
                    'text': '\n'.join(
                        [
                            'Function Helper',
                            '    Return 1',
                            'End',
                            'Hel',
                        ]
                    )
                }
            ],
        }
    )

    result = server._on_completion(
        {
            'textDocument': {'uri': uri},
            'position': {'line': 3, 'character': 3},
        }
    )

    labels = [item['label'] for item in result['items']]
    assert 'Helper' in labels


def test_lsp_analysis_failure_becomes_diagnostic(monkeypatch):
    server = _server(debounce=0.0)
    uri = 'file:///broken.epl'

    def explode(_text):
        raise RuntimeError('boom')

    monkeypatch.setattr(server.analyzer, 'analyze_text', explode)

    server._on_did_change(
        {
            'textDocument': {'uri': uri},
            'contentChanges': [{'text': 'Print "hello"'}],
        }
    )

    diagnostics = server.analyzer.diagnostics[uri]
    assert server.analyzer.documents[uri] == 'Print "hello"'
    assert any('Analysis failed: boom' in diag['message'] for diag in diagnostics)


def test_lsp_analysis_timeout_becomes_diagnostic(monkeypatch):
    server = _server(debounce=0.0, timeout=0.01)
    uri = 'file:///slow.epl'

    def slow(_text):
        time.sleep(0.05)
        return [], []

    monkeypatch.setattr(server.analyzer, 'analyze_text', slow)

    server._on_did_change(
        {
            'textDocument': {'uri': uri},
            'contentChanges': [{'text': 'Print "hello"'}],
        }
    )

    diagnostics = server.analyzer.diagnostics[uri]
    assert any('timed out' in diag['message'].lower() for diag in diagnostics)
