"""
EPL Lexer (Tokenizer)
Converts EPL source code into a stream of tokens.
Handles English keywords, multi-word phrases, symbolic operators, and literals.
"""

from epl.tokens import Token, TokenType, KEYWORDS, MULTI_WORD_KEYWORDS
from epl.errors import LexerError


class Lexer:
    """Tokenizes EPL source code into a list of Tokens."""

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens = []

    def tokenize(self) -> list:
        """Convert entire source into a list of tokens."""
        while self.pos < len(self.source):
            ch = self.source[self.pos]

            # Skip spaces and tabs (not newlines)
            if ch in (' ', '\t'):
                self._advance()
                continue

            # Newlines
            if ch == '\n':
                self.tokens.append(Token(TokenType.NEWLINE, '\\n', self.line, self.column))
                self._advance()
                self.line += 1
                self.column = 1
                continue

            # Carriage return (handle \r\n)
            if ch == '\r':
                self._advance()
                if self.pos < len(self.source) and self.source[self.pos] == '\n':
                    self._advance()
                self.tokens.append(Token(TokenType.NEWLINE, '\\n', self.line, self.column))
                self.line += 1
                self.column = 1
                continue

            # Comments: Note: ...
            if ch.lower() == 'n' and self._match_word("note"):
                if self.pos + 4 < len(self.source) and self.source[self.pos + 4] == ':':
                    self._skip_comment()
                    continue

            # Strings
            if ch == '"':
                self._read_string()
                continue

            # Numbers
            if ch.isdigit():
                self._read_number()
                continue

            # Identifiers and keywords
            if ch.isalpha() or ch == '_':
                self._read_identifier()
                continue

            # Symbolic operators
            if ch == '+':
                if self._peek_next() == '=':
                    self.tokens.append(Token(TokenType.OP_PLUS_ASSIGN, '+=', self.line, self.column))
                    self._advance()
                    self._advance()
                else:
                    self.tokens.append(Token(TokenType.OP_PLUS, '+', self.line, self.column))
                    self._advance()
                continue
            if ch == '-':
                if self._peek_next() == '>':
                    self.tokens.append(Token(TokenType.ARROW, '->', self.line, self.column))
                    self._advance()
                    self._advance()
                elif self._peek_next() == '=':
                    self.tokens.append(Token(TokenType.OP_MINUS_ASSIGN, '-=', self.line, self.column))
                    self._advance()
                    self._advance()
                else:
                    self.tokens.append(Token(TokenType.OP_MINUS, '-', self.line, self.column))
                    self._advance()
                continue
            if ch == '*':
                if self._peek_next() == '*':
                    self.tokens.append(Token(TokenType.OP_POWER, '**', self.line, self.column))
                    self._advance()
                    self._advance()
                elif self._peek_next() == '=':
                    self.tokens.append(Token(TokenType.OP_MUL_ASSIGN, '*=', self.line, self.column))
                    self._advance()
                    self._advance()
                else:
                    self.tokens.append(Token(TokenType.OP_MULTIPLY, '*', self.line, self.column))
                    self._advance()
                continue
            if ch == '/':
                if self._peek_next() == '/':
                    self.tokens.append(Token(TokenType.OP_FLOOR_DIV, '//', self.line, self.column))
                    self._advance()
                    self._advance()
                elif self._peek_next() == '=':
                    self.tokens.append(Token(TokenType.OP_DIV_ASSIGN, '/=', self.line, self.column))
                    self._advance()
                    self._advance()
                else:
                    self.tokens.append(Token(TokenType.OP_DIVIDE, '/', self.line, self.column))
                    self._advance()
                continue
            if ch == '%':
                if self._peek_next() == '=':
                    self.tokens.append(Token(TokenType.OP_MOD_ASSIGN, '%=', self.line, self.column))
                    self._advance()
                    self._advance()
                else:
                    self.tokens.append(Token(TokenType.OP_MODULO, '%', self.line, self.column))
                    self._advance()
                continue

            # Comparison / assignment operators
            if ch == '=':
                if self._peek_next() == '=':
                    self.tokens.append(Token(TokenType.OP_EQUAL, '==', self.line, self.column))
                    self._advance()
                    self._advance()
                else:
                    self.tokens.append(Token(TokenType.OP_ASSIGN, '=', self.line, self.column))
                    self._advance()
                continue
            if ch == '!':
                if self._peek_next() == '=':
                    self.tokens.append(Token(TokenType.OP_NOT_EQUAL, '!=', self.line, self.column))
                    self._advance()
                    self._advance()
                else:
                    raise LexerError(f'Unexpected character "!"', self.line, self.column)
                continue
            if ch == '>':
                if self._peek_next() == '=':
                    self.tokens.append(Token(TokenType.OP_GREATER_EQ, '>=', self.line, self.column))
                    self._advance()
                    self._advance()
                else:
                    self.tokens.append(Token(TokenType.OP_GREATER, '>', self.line, self.column))
                    self._advance()
                continue
            if ch == '<':
                if self._peek_next() == '=':
                    self.tokens.append(Token(TokenType.OP_LESS_EQ, '<=', self.line, self.column))
                    self._advance()
                    self._advance()
                else:
                    self.tokens.append(Token(TokenType.OP_LESS, '<', self.line, self.column))
                    self._advance()
                continue

            # Delimiters
            if ch == '.':
                self.tokens.append(Token(TokenType.DOT, '.', self.line, self.column))
                self._advance()
                continue
            if ch == ',':
                self.tokens.append(Token(TokenType.COMMA, ',', self.line, self.column))
                self._advance()
                continue
            if ch == '(':
                self.tokens.append(Token(TokenType.LPAREN, '(', self.line, self.column))
                self._advance()
                continue
            if ch == ')':
                self.tokens.append(Token(TokenType.RPAREN, ')', self.line, self.column))
                self._advance()
                continue
            if ch == '[':
                self.tokens.append(Token(TokenType.LBRACKET, '[', self.line, self.column))
                self._advance()
                continue
            if ch == ']':
                self.tokens.append(Token(TokenType.RBRACKET, ']', self.line, self.column))
                self._advance()
                continue
            if ch == ':':
                if self._peek_next() == ':':
                    self.tokens.append(Token(TokenType.DOUBLE_COLON, '::', self.line, self.column))
                    self._advance()
                    self._advance()
                else:
                    self.tokens.append(Token(TokenType.COLON, ':', self.line, self.column))
                    self._advance()
                continue
            if ch == '{':
                self.tokens.append(Token(TokenType.LBRACE, '{', self.line, self.column))
                self._advance()
                continue
            if ch == '}':
                self.tokens.append(Token(TokenType.RBRACE, '}', self.line, self.column))
                self._advance()
                continue
            if ch == '|':
                self.tokens.append(Token(TokenType.PIPE, '|', self.line, self.column))
                self._advance()
                continue
            if ch == '?':
                self.tokens.append(Token(TokenType.QUESTION, '?', self.line, self.column))
                self._advance()
                continue

            raise LexerError(f'Unexpected character "{ch}"', self.line, self.column)

        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        # Post-process: resolve multi-word keywords
        self.tokens = self._resolve_multi_word_keywords(self.tokens)
        return self.tokens

    def _advance(self):
        """Move to the next character."""
        self.pos += 1
        self.column += 1

    def _peek_next(self) -> str:
        """Look at next character without consuming."""
        if self.pos + 1 < len(self.source):
            return self.source[self.pos + 1]
        return ''

    def _match_word(self, word: str) -> bool:
        """Check if source at current pos starts with a word (case-insensitive)."""
        end = self.pos + len(word)
        if end > len(self.source):
            return False
        if self.source[self.pos:end].lower() != word:
            return False
        # Make sure it's a full word (not part of a larger identifier)
        if end < len(self.source) and (self.source[end].isalnum() or self.source[end] == '_'):
            return False
        return True

    def _skip_comment(self):
        """Skip a comment line (Note: ...)."""
        while self.pos < len(self.source) and self.source[self.pos] != '\n':
            self._advance()

    def _read_string(self):
        """Read a double-quoted string literal (single or triple-quoted)."""
        start_line = self.line
        start_col = self.column

        # Check for triple-quote (multi-line string)
        if (self.pos + 2 < len(self.source)
                and self.source[self.pos:self.pos + 3] == '"""'):
            self._read_triple_string(start_line, start_col)
            return

        self._advance()  # skip opening "
        result = []

        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch == '"':
                self._advance()  # skip closing "
                self.tokens.append(Token(TokenType.STRING, ''.join(result), start_line, start_col))
                return
            if ch == '\\':
                self._advance()
                if self.pos < len(self.source):
                    esc_ch = self.source[self.pos]
                    resolved = self._resolve_escape(esc_ch, start_line, start_col)
                    if resolved is not None:
                        result.append(resolved)
                    else:
                        result.append('\\')
                        result.append(esc_ch)
                    self._advance()
                continue
            if ch == '\n':
                raise LexerError('String literal not closed before end of line.', start_line, start_col)
            result.append(ch)
            self._advance()

        raise LexerError('String literal not closed before end of file.', start_line, start_col)

    def _read_triple_string(self, start_line, start_col):
        """Read a triple-quoted multi-line string \"\"\"...\"\"\"."""
        self._advance()  # skip first "
        self._advance()  # skip second "
        self._advance()  # skip third "
        result = []

        while self.pos < len(self.source):
            ch = self.source[self.pos]
            # Check for closing triple-quote
            if (ch == '"' and self.pos + 2 < len(self.source)
                    and self.source[self.pos + 1] == '"'
                    and self.source[self.pos + 2] == '"'):
                self._advance()  # skip first "
                self._advance()  # skip second "
                self._advance()  # skip third "
                self.tokens.append(Token(TokenType.STRING, ''.join(result), start_line, start_col))
                return
            if ch == '\\':
                self._advance()
                if self.pos < len(self.source):
                    esc_ch = self.source[self.pos]
                    resolved = self._resolve_escape(esc_ch, start_line, start_col)
                    if resolved is not None:
                        result.append(resolved)
                    else:
                        result.append('\\')
                        result.append(esc_ch)
                    self._advance()
                continue
            if ch == '\n':
                self.line += 1
                self.column = 1
            result.append(ch)
            self._advance()

        raise LexerError('Triple-quoted string not closed before end of file.', start_line, start_col)

    def _resolve_escape(self, escape_char: str, start_line: int, start_col: int) -> str:
        """Resolve an escape sequence character. Returns the resolved char or None for unknown."""
        simple = {'n': '\n', 't': '\t', '"': '"', '\\': '\\', 'r': '\r', '0': '\0', '$': '$', 'a': '\a', 'b': '\b', 'f': '\f', 'v': '\v'}
        if escape_char in simple:
            return simple[escape_char]
        # \xNN hex escape
        if escape_char == 'x':
            hex_str = self.source[self.pos + 1:self.pos + 3]
            if len(hex_str) == 2 and all(c in '0123456789abcdefABCDEF' for c in hex_str):
                self._advance()  # skip first hex digit
                self._advance()  # skip second hex digit
                return chr(int(hex_str, 16))
            raise LexerError(f'Invalid hex escape "\\x{hex_str}".', start_line, start_col)
        # \uXXXX unicode escape
        if escape_char == 'u':
            uni_str = self.source[self.pos + 1:self.pos + 5]
            if len(uni_str) == 4 and all(c in '0123456789abcdefABCDEF' for c in uni_str):
                for _ in range(4):
                    self._advance()
                return chr(int(uni_str, 16))
            raise LexerError(f'Invalid unicode escape "\\u{uni_str}".', start_line, start_col)
        return None

    def _read_number(self):
        """Read an integer or decimal number. Supports hex (0x), octal (0o), binary (0b), and underscores."""
        start_col = self.column
        first_ch = self.source[self.pos]

        # Check for 0x, 0o, 0b prefixes
        if first_ch == '0' and self.pos + 1 < len(self.source):
            prefix = self.source[self.pos + 1]
            if prefix in ('x', 'X'):
                return self._read_prefixed_number('0x', '0123456789abcdefABCDEF', 16, start_col)
            if prefix in ('o', 'O'):
                return self._read_prefixed_number('0o', '01234567', 8, start_col)
            if prefix in ('b', 'B'):
                return self._read_prefixed_number('0b', '01', 2, start_col)

        num_str = []
        has_dot = False

        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch.isdigit():
                num_str.append(ch)
                self._advance()
            elif ch == '_' and num_str and self.pos + 1 < len(self.source) and self.source[self.pos + 1].isdigit():
                self._advance()  # skip underscore separator
            elif ch == '.' and not has_dot:
                # Check if next char is a digit (decimal point vs statement dot)
                if self.pos + 1 < len(self.source) and self.source[self.pos + 1].isdigit():
                    has_dot = True
                    num_str.append(ch)
                    self._advance()
                else:
                    break
            else:
                break

        value_str = ''.join(num_str)
        if has_dot:
            self.tokens.append(Token(TokenType.NUMBER, float(value_str), self.line, start_col))
        else:
            self.tokens.append(Token(TokenType.NUMBER, int(value_str), self.line, start_col))

    def _read_prefixed_number(self, prefix: str, valid_chars: str, base: int, start_col: int):
        """Read a hex, octal, or binary integer literal."""
        self._advance()  # skip '0'
        self._advance()  # skip prefix letter
        digits = []
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch in valid_chars:
                digits.append(ch)
                self._advance()
            elif ch == '_' and digits and self.pos + 1 < len(self.source) and self.source[self.pos + 1] in valid_chars:
                self._advance()  # skip underscore separator
            else:
                break
        if not digits:
            raise LexerError(f'Invalid {prefix} literal: no digits after prefix.', self.line, start_col)
        self.tokens.append(Token(TokenType.NUMBER, int(''.join(digits), base), self.line, start_col))

    def _read_identifier(self):
        """Read an identifier or keyword."""
        start_col = self.column
        chars = []

        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch.isalnum() or ch == '_':
                chars.append(ch)
                self._advance()
            else:
                break

        word = ''.join(chars)
        lower_word = word.lower()

        # Check if it's a keyword
        if lower_word in KEYWORDS:
            self.tokens.append(Token(KEYWORDS[lower_word], word, self.line, start_col))
        else:
            self.tokens.append(Token(TokenType.IDENTIFIER, word, self.line, start_col))

    def _resolve_multi_word_keywords(self, tokens: list) -> list:
        """
        Post-process token list to merge multi-word keyword sequences.
        e.g., [IS, GREATER, THAN] → [IS_GREATER_THAN]
        """
        result = []
        i = 0

        while i < len(tokens):
            matched = False

            for phrase, token_type in MULTI_WORD_KEYWORDS:
                phrase_len = len(phrase)
                if i + phrase_len <= len(tokens):
                    # Check if the next N tokens match this phrase
                    match = True
                    for j, keyword in enumerate(phrase):
                        tok = tokens[i + j]
                        if not isinstance(tok.value, str) or tok.value.lower() != keyword:
                            match = False
                            break
                    if match:
                        # Merge into single token
                        combined_value = ' '.join(str(t.value) for t in tokens[i:i + phrase_len])
                        result.append(Token(token_type, combined_value, tokens[i].line, tokens[i].column))
                        i += phrase_len
                        matched = True
                        break

            if not matched:
                result.append(tokens[i])
                i += 1

        return result
