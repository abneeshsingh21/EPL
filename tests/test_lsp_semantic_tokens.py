"""Tests for LSP v2 semantic tokens and token-aware references/rename."""

import io

from epl.lsp_server import JSONRPC, EPLAnalyzer, EPLLanguageServer


def _server():
    return EPLLanguageServer(
        JSONRPC(reader=io.BytesIO(b''), writer=io.BytesIO()),
        change_debounce_seconds=0.0,
        analysis_timeout_seconds=1.0,
    )


def _analyzer_with(source, uri='file:///t.epl'):
    a = EPLAnalyzer()
    a.update_document(uri, source)
    return a, uri


def _decode(data):
    """Decode the LSP delta-encoded semantic token stream into absolute tuples.

    Returns list of (line, col, length, type_index, modifiers).
    """
    out = []
    line = 0
    col = 0
    for i in range(0, len(data), 5):
        d_line, d_col, length, type_index, mods = data[i : i + 5]
        if d_line == 0:
            col += d_col
        else:
            line += d_line
            col = d_col
        out.append((line, col, length, type_index, mods))
    return out


def test_legend_is_stable():
    # The client maps integer indices to names by position; order must not drift.
    assert EPLAnalyzer.SEMANTIC_TOKEN_TYPES[0] == 'keyword'
    assert EPLAnalyzer.SEMANTIC_TOKEN_TYPES[6] == 'string'
    assert EPLAnalyzer.SEMANTIC_TOKEN_TYPES[7] == 'comment'


def test_initialize_advertises_semantic_tokens():
    server = _server()
    caps = server._on_initialize({})['capabilities']
    provider = caps['semanticTokensProvider']
    assert provider['full'] is True
    assert provider['legend']['tokenTypes'] == EPLAnalyzer.SEMANTIC_TOKEN_TYPES


def test_semantic_tokens_data_is_multiple_of_five():
    a, uri = _analyzer_with('Create x = 5\nPrint x\n')
    data = a.get_semantic_tokens(uri)['data']
    assert data, 'expected some tokens'
    assert len(data) % 5 == 0


def test_number_literal_classified_as_number():
    a, uri = _analyzer_with('Create x = 42\n')
    tokens = _decode(a.get_semantic_tokens(uri)['data'])
    number_idx = EPLAnalyzer.SEMANTIC_TOKEN_TYPES.index('number')
    # The literal 42 sits at line 0; find a token of length 2 typed as number.
    assert any(t[2] == 2 and t[3] == number_idx for t in tokens)


def test_string_literal_classified_as_string_with_quotes():
    src = 'Print "hello"\n'
    a, uri = _analyzer_with(src)
    tokens = _decode(a.get_semantic_tokens(uri)['data'])
    string_idx = EPLAnalyzer.SEMANTIC_TOKEN_TYPES.index('string')
    # "hello" including quotes = 7 chars, starting at column 6.
    assert any(t[1] == 6 and t[2] == 7 and t[3] == string_idx for t in tokens)


def test_comment_classified_as_comment():
    src = 'Print 1  # this is a note\n'
    a, uri = _analyzer_with(src)
    tokens = _decode(a.get_semantic_tokens(uri)['data'])
    comment_idx = EPLAnalyzer.SEMANTIC_TOKEN_TYPES.index('comment')
    assert any(t[3] == comment_idx for t in tokens)


def test_note_comment_classified_as_comment():
    src = 'Note: this whole line is a comment\nPrint 1\n'
    a, uri = _analyzer_with(src)
    tokens = _decode(a.get_semantic_tokens(uri)['data'])
    comment_idx = EPLAnalyzer.SEMANTIC_TOKEN_TYPES.index('comment')
    # The comment is on line 0 and spans the line.
    assert any(t[0] == 0 and t[3] == comment_idx for t in tokens)


def test_function_name_classified_as_function():
    src = '\n'.join(['Function greet', '    Return 1', 'End', 'Call greet', ''])
    a, uri = _analyzer_with(src)
    tokens = _decode(a.get_semantic_tokens(uri)['data'])
    func_idx = EPLAnalyzer.SEMANTIC_TOKEN_TYPES.index('function')
    assert any(t[3] == func_idx for t in tokens)


def test_keyword_inside_string_is_not_a_keyword():
    # "Print" appears as a keyword on line 0 and as string content on line 1.
    src = 'Print 1\nCreate s = "Print this"\n'
    a, uri = _analyzer_with(src)
    tokens = _decode(a.get_semantic_tokens(uri)['data'])
    keyword_idx = EPLAnalyzer.SEMANTIC_TOKEN_TYPES.index('keyword')
    string_idx = EPLAnalyzer.SEMANTIC_TOKEN_TYPES.index('string')
    # No keyword token should start inside the string region on line 1.
    line1_keywords = [t for t in tokens if t[0] == 1 and t[3] == keyword_idx and t[1] >= 11]
    assert not line1_keywords
    assert any(t[0] == 1 and t[3] == string_idx for t in tokens)


def test_references_skip_string_and_comment_occurrences():
    src = '\n'.join(
        [
            'Create total = 5',  # line 0: real var, col 7
            'Print total',       # line 1: real use,  col 6
            'Print "total is big"',  # line 2: inside string — must be ignored
            '# total here too',  # line 3: inside comment — must be ignored
            '',
        ]
    )
    a, uri = _analyzer_with(src)
    refs = a.get_references(uri, 0, 7)
    ref_lines = sorted(r['range']['start']['line'] for r in refs)
    assert ref_lines == [0, 1]


def test_rename_only_touches_real_identifiers():
    src = '\n'.join(
        [
            'Create count = 0',
            'Set count to count plus 1',
            'Print "count unchanged in string"',
            '',
        ]
    )
    a, uri = _analyzer_with(src)
    edits = a.get_rename_edits(uri, 0, 7, 'total')
    changes = edits['changes'][uri]
    # count appears 3 times as an identifier (decl + two uses), 0 times in string.
    assert len(changes) == 3
    for edit in changes:
        assert edit['newText'] == 'total'
        # No edit should land on the string line (line 2).
        assert edit['range']['start']['line'] != 2


def test_semantic_tokens_handler_roundtrip():
    server = _server()
    uri = 'file:///rt.epl'
    server._on_did_open(
        {'textDocument': {'uri': uri, 'text': 'Create x = 1\nPrint x\n'}}
    )
    result = server._on_semantic_tokens({'textDocument': {'uri': uri}})
    assert 'data' in result
    assert len(result['data']) % 5 == 0


def test_semantic_tokens_on_unlexable_source_degrades_gracefully():
    # Unterminated string should not raise; comments/strings still emitted.
    a, uri = _analyzer_with('Print "unterminated\n')
    result = a.get_semantic_tokens(uri)
    assert 'data' in result
    assert len(result['data']) % 5 == 0
