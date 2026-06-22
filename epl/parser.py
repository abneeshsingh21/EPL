"""
EPL Parser (v0.2 - Simplified Syntax)
Recursive-descent parser that converts a token stream into an AST.

Simplifications in v0.2:
  - Periods are OPTIONAL (newlines end statements)
  - Block endings: just "End" works (no need for "End if", "End repeat", etc.)
  - Shorthand variables: "age = 20" works alongside "Create age equal to 20"
  - Simpler functions: "Function add takes a and b" works
"""

from epl import ast_nodes as ast
from epl.errors import ParserError
from epl.tokens import Token, TokenType


class Parser:
    """Parses EPL tokens into an Abstract Syntax Tree."""

    MAX_DEPTH = 200  # Maximum recursion depth for nested expressions

    def __init__(self, tokens: list):
        self.tokens = tokens
        self.pos = 0
        self._depth = 0
        self.errors: list = []  # collected parse errors for recovery mode
        self.max_errors = 20  # stop collecting after this many

    # ─── Helpers ──────────────────────────────────────────

    def _current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token(TokenType.EOF, None, -1, -1)

    def _peek(self, offset: int = 1) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return Token(TokenType.EOF, None, -1, -1)

    def _advance(self) -> Token:
        tok = self._current()
        self.pos += 1
        return tok

    def _expect(self, token_type: TokenType, error_msg: str = None) -> Token:
        tok = self._current()
        if tok.type != token_type:
            msg = (
                error_msg
                or f'Expected {token_type.name} but found {tok.type.name} ("{tok.value}").'
            )
            raise ParserError(msg, tok.line)
        return self._advance()

    def _match(self, *types) -> bool:
        return self._current().type in types

    def _skip_newlines(self):
        while self._current().type == TokenType.NEWLINE:
            self._advance()

    def _optional(self, *types) -> 'Token | None':
        if self._current().type in types:
            return self._advance()
        return None

    def _end_statement(self):
        """Consume optional period and/or newline at end of statement."""
        self._optional(TokenType.DOT)
        # Consume newlines (or EOF is fine too)
        while self._match(TokenType.NEWLINE):
            self._advance()

    # Soft keywords that can also serve as identifiers in name positions
    _SOFT_KEYWORDS = (
        TokenType.A,
        TokenType.AN,
        TokenType.THE,
        TokenType.TO,
        TokenType.OF,
        TokenType.BY,
        TokenType.AS,
        TokenType.TYPE,
        TokenType.VARIABLE,
        TokenType.NAMED,
        TokenType.FROM,
        TokenType.THAT,
        TokenType.WITH,
        # v0.6: Allow these keywords as method/property names
        TokenType.MAP,
        TokenType.REPEAT,
        TokenType.STEP,
        TokenType.TYPEOF,
        TokenType.SET,
        # v0.7: English aliases
        TokenType.SAY,
        TokenType.ASK,
        TokenType.REMEMBER,
        TokenType.RAISED,
        TokenType.BETWEEN,
        TokenType.ADD_KW,
        TokenType.SORT_KW,
        TokenType.REVERSE_KW,
        # v0.7.1: Simplified operators
        TokenType.MOD_KW,
        TokenType.EQUALS_KW,
        TokenType.MULTIPLY_KW,
        TokenType.DIVIDE_KW,
        TokenType.GIVEN,
        # v1.4: GUI/web/async keywords usable as identifiers in context
        TokenType.ROW,
        TokenType.COLUMN,
        TokenType.LABEL,
        TokenType.TAB,
        TokenType.TREE,
        TokenType.MENU_KW,
        TokenType.START,
        TokenType.PORT,
        TokenType.ROUTE,
        TokenType.ON,
        TokenType.BUTTON,
        TokenType.CALLED,
        TokenType.DOES,
        TokenType.ACTION,
        TokenType.NOTHING,
        # v6.0: Style & Layout keywords usable as identifiers in context
        TokenType.STYLE,
        TokenType.COMPONENT,
        TokenType.DIV,
        TokenType.SECTION,
        TokenType.NAV,
        TokenType.HEADER_EL,
        TokenType.FOOTER_EL,
        TokenType.SPAN,
        TokenType.ARTICLE,
        TokenType.ASIDE,
        TokenType.MAIN_EL,
        TokenType.CONTAINER,
        TokenType.GRID,
        TokenType.FLEX,
        TokenType.ANIMATE,
        TokenType.DURATION,
        TokenType.EASING,
        TokenType.KEYFRAME,
        TokenType.TRANSITION_KW,
        TokenType.TRANSFORM,
        TokenType.OPACITY,
        TokenType.RESPONSIVE,
        TokenType.CLASSNAME,
        TokenType.APPLY,
        # v9.3.0: Raw HTML escape hatch — these must remain usable as identifiers
        # (`html = ""` is common in legacy code; `raw` is also a frequent var name).
        TokenType.RAW,
        TokenType.HTML_KW,
        # v6.1: 3D & Canvas keywords usable as identifiers
        TokenType.SCENE,
        TokenType.CAMERA_KW,
        TokenType.MESH,
        TokenType.LIGHT,
        TokenType.MATERIAL,
        TokenType.TEXTURE,
        TokenType.RENDER,
        TokenType.POSITION,
        TokenType.ROTATION,
        TokenType.SCALE_KW,
        TokenType.DRAW,
        TokenType.FILL,
        TokenType.STROKE,
        # v9.8.0: words that are reserved tokens but read naturally as
        # function/parameter/member names. Required by the bundled stdlib
        # wrappers (regex.match, net.fetch, sql.delete, sql ... where ...).
        # These are only ever dispatched as statements by token *type*, so
        # allowing them in identifier positions does not affect statements.
        TokenType.MATCH,
        TokenType.FETCH,
        TokenType.DELETE_KW,
        TokenType.WHERE,
    )

    def _expect_identifier(self, error_msg: str = None) -> Token:
        tok = self._current()
        if tok.type == TokenType.IDENTIFIER:
            return self._advance()
        if tok.type in self._SOFT_KEYWORDS:
            self._advance()
            return Token(TokenType.IDENTIFIER, tok.value, tok.line, tok.column)
        msg = error_msg or f'Expected an identifier but found {tok.type.name} ("{tok.value}").'
        raise ParserError(msg, tok.line)

    def _match_identifier(self) -> bool:
        return (
            self._current().type == TokenType.IDENTIFIER
            or self._current().type in self._SOFT_KEYWORDS
        )

    def _is_block_end(self) -> bool:
        """Check if current token is any kind of block terminator."""
        return self._match(
            TokenType.END,
            TokenType.END_IF,
            TokenType.END_WHILE,
            TokenType.END_REPEAT,
            TokenType.END_FOR,
            TokenType.END_FUNCTION,
            TokenType.OTHERWISE,
            TokenType.EOF,
            TokenType.CATCH,
            TokenType.WHEN,
            TokenType.DEFAULT,
        )

    def _consume_block_end(self):
        """Consume any block ending: End, End if, End while, End repeat, End for, End function."""
        if self._match(TokenType.END):
            self._advance()
        elif self._match(
            TokenType.END_IF,
            TokenType.END_WHILE,
            TokenType.END_REPEAT,
            TokenType.END_FOR,
            TokenType.END_FUNCTION,
        ):
            self._advance()
        else:
            raise ParserError('Expected "End" to close this block.', self._current().line)
        self._end_statement()

    # ─── Error Recovery ────────────────────────────────────

    # Token types that begin a new statement (synchronization points)
    _SYNC_TOKENS = frozenset(
        {
            TokenType.CREATE,
            TokenType.SET,
            TokenType.PRINT,
            TokenType.DISPLAY,
            TokenType.SHOW,
            TokenType.SAY,
            TokenType.IF,
            TokenType.WHILE,
            TokenType.FOR,
            TokenType.REPEAT,
            TokenType.FUNCTION,
            TokenType.CLASS,
            TokenType.RETURN,
            TokenType.IMPORT,
            TokenType.TRY,
            TokenType.THROW,
            TokenType.ASSERT,
            TokenType.BREAK,
            TokenType.CONTINUE,
            TokenType.END,
            TokenType.EOF,
        }
    )

    def _synchronize(self):
        """Advance past tokens until we reach a likely statement boundary.
        Used for error recovery so the parser can continue after an error."""
        self._advance()  # skip the bad token
        while not self._match(TokenType.EOF):
            # A newline followed by a statement-starter is a good sync point
            if self._current().type == TokenType.NEWLINE:
                self._advance()
                if self._current().type in self._SYNC_TOKENS:
                    return
                continue
            # Direct statement-starting keyword
            if self._current().type in self._SYNC_TOKENS:
                return
            self._advance()

    # ─── Main Entry ───────────────────────────────────────

    def parse(self) -> ast.Program:
        """Parse token stream into AST. Collects multiple errors via recovery."""
        statements = []
        self._skip_newlines()

        while not self._match(TokenType.EOF):
            try:
                stmt = self._parse_statement()
                if stmt:
                    statements.append(stmt)
            except ParserError as e:
                self.errors.append(e)
                if len(self.errors) >= self.max_errors:
                    break
                self._synchronize()
            self._skip_newlines()

        # If we collected errors, raise the first one (with count info)
        if self.errors:
            if len(self.errors) == 1:
                raise self.errors[0]
            first = self.errors[0]
            msg = f'{first.message}\n  ... and {len(self.errors) - 1} more error(s). Fix the above and re-run.'
            raise ParserError(msg, first.line)

        return ast.Program(statements)

    def parse_with_recovery(self):
        """Parse and return (program, errors) tuple without raising.
        The returned program contains all successfully parsed statements.
        Errors list may be empty (success) or contain ParserError instances."""
        statements = []
        self._skip_newlines()
        while not self._match(TokenType.EOF):
            try:
                stmt = self._parse_statement()
                if stmt:
                    statements.append(stmt)
            except ParserError as e:
                self.errors.append(e)
                if len(self.errors) >= self.max_errors:
                    break
                self._synchronize()
            self._skip_newlines()
        return ast.Program(statements), list(self.errors)

    # ─── Statement Parsing ────────────────────────────────

    def _parse_statement(self):
        self._skip_newlines()
        tok = self._current()

        if tok.type == TokenType.EOF:
            return None

        if tok.type == TokenType.SET:
            return self._parse_var_assignment()

        if tok.type in (TokenType.PRINT, TokenType.DISPLAY, TokenType.SHOW, TokenType.SAY):
            return self._parse_print()

        if tok.type == TokenType.INPUT:
            return self._parse_input()

        if tok.type == TokenType.ASK:
            return self._parse_ask()

        if tok.type == TokenType.COMMENT:
            return self._parse_comment()

        if tok.type == TokenType.IF:
            return self._parse_if()

        if tok.type == TokenType.WHILE:
            return self._parse_while()

        if tok.type == TokenType.REPEAT:
            return self._parse_repeat()

        if tok.type == TokenType.FOR:
            return self._parse_for()

        if tok.type == TokenType.DEFINE:
            return self._parse_function_def()

        if tok.type == TokenType.FUNCTION:
            return self._parse_function_def_short()

        if tok.type == TokenType.CALL:
            return self._parse_call_statement()

        if tok.type == TokenType.RETURN:
            return self._parse_return()

        if tok.type == TokenType.INCREASE:
            return self._parse_increase()

        if tok.type == TokenType.DECREASE:
            return self._parse_decrease()

        # Shared tuple for peek-ahead assignment detection (used by keyword-as-statement dispatch)
        _assign_types = (
            TokenType.OP_ASSIGN,
            TokenType.OP_PLUS_ASSIGN,
            TokenType.OP_MINUS_ASSIGN,
            TokenType.OP_MUL_ASSIGN,
            TokenType.OP_DIV_ASSIGN,
            TokenType.OP_MOD_ASSIGN,
        )

        # v0.7.1: Multiply/Divide English statements
        if tok.type == TokenType.MULTIPLY_KW:
            nxt = self._peek()
            if not (nxt and nxt.type in _assign_types):
                return self._parse_multiply_by()

        if tok.type == TokenType.DIVIDE_KW:
            nxt = self._peek()
            if not (nxt and nxt.type in _assign_types):
                return self._parse_divide_by()

        # v0.2: File I/O
        if tok.type == TokenType.WRITE:
            return self._parse_write()

        if tok.type == TokenType.APPEND:
            return self._parse_append()

        # v0.2: Class definition
        if tok.type == TokenType.CLASS:
            return self._parse_class_def()

        # v0.3: Try/Catch
        if tok.type == TokenType.TRY:
            return self._parse_try_catch()

        # v0.3: Break/Continue
        if tok.type == TokenType.BREAK:
            self._advance()
            self._end_statement()
            return ast.BreakStatement(tok.line)

        if tok.type == TokenType.CONTINUE:
            self._advance()
            self._end_statement()
            return ast.ContinueStatement(tok.line)

        # v0.3: Match/When
        if tok.type == TokenType.MATCH:
            return self._parse_match()

        # v0.3: Import EPL file
        if tok.type == TokenType.IMPORT:
            return self._parse_import()

        # v0.3: Use python library
        if tok.type == TokenType.USE:
            return self._parse_use()

        # v0.3: Wait
        if tok.type == TokenType.WAIT:
            return self._parse_wait()

        # v0.3: Exit
        if tok.type == TokenType.EXIT_KW:
            self._advance()
            self._end_statement()
            return ast.ExitStatement(tok.line)

        # v0.3: Constant
        if tok.type == TokenType.CONSTANT:
            return self._parse_constant()

        # v0.3: Assert
        if tok.type == TokenType.ASSERT:
            return self._parse_assert()

        # v0.3: Multi-line comment (NoteBlock)
        if tok.type == TokenType.NOTEBLOCK:
            return self._parse_noteblock()

        # v0.5: Web Framework
        if tok.type == TokenType.ROUTE:
            return self._parse_route()

        if tok.type == TokenType.START:
            return self._parse_start_server()

        if tok.type == TokenType.PAGE:
            return self._parse_page()

        if tok.type == TokenType.SEND:
            return self._parse_send()

        if tok.type == TokenType.SCRIPT:
            return self._parse_script()

        if tok.type == TokenType.STORE:
            return self._parse_store()

        if tok.type == TokenType.FETCH:
            return self._parse_fetch()

        if tok.type == TokenType.DELETE_KW:
            return self._parse_delete()

        if tok.type == TokenType.REDIRECT:
            return self._parse_redirect()

        # v0.6: Enum
        if tok.type == TokenType.ENUM:
            return self._parse_enum()

        # v0.6: Throw
        if tok.type == TokenType.THROW:
            return self._parse_throw()

        # v0.7: English list operations
        # Peek ahead: if followed by '=' or augmented assign, treat as variable name
        if tok.type == TokenType.ADD_KW:
            nxt = self._peek()
            if not (nxt and nxt.type in _assign_types):
                return self._parse_add_to()

        if tok.type == TokenType.SORT_KW:
            nxt = self._peek()
            if not (nxt and nxt.type in _assign_types):
                return self._parse_sort_statement()

        if tok.type == TokenType.REVERSE_KW:
            nxt = self._peek()
            if not (nxt and nxt.type in _assign_types):
                return self._parse_reverse_statement()

        # v1.4: GUI Framework
        if tok.type == TokenType.WINDOW:
            return self._parse_window()

        if tok.type == TokenType.ROW:
            return self._parse_layout_block('row')

        if tok.type == TokenType.COLUMN:
            return self._parse_layout_block('column')

        if tok.type == TokenType.BIND:
            return self._parse_bind_event()

        if tok.type == TokenType.DIALOG:
            return self._parse_dialog()

        if tok.type == TokenType.MENU_KW:
            return self._parse_menu_def()

        if tok.type == TokenType.CANVAS_KW:
            return self._parse_canvas_draw()

        # GUI widget keywords as statements
        if tok.type == TokenType.LABEL:
            return self._parse_widget_add('label')
        if tok.type == TokenType.TEXTBOX:
            return self._parse_widget_add('input')
        if tok.type == TokenType.CHECKBOX_KW:
            return self._parse_widget_add('checkbox')
        if tok.type == TokenType.DROPDOWN_KW:
            return self._parse_widget_add('dropdown')
        if tok.type == TokenType.SLIDER_KW:
            return self._parse_widget_add('slider')
        if tok.type == TokenType.PROGRESS_KW:
            return self._parse_widget_add('progress')
        if tok.type == TokenType.TEXTAREA_KW:
            return self._parse_widget_add('textarea')

        # Button is shared with web, check context
        if tok.type == TokenType.BUTTON:
            nxt = self._peek()
            if nxt and nxt.type == TokenType.STRING:
                return self._parse_widget_add('button')

        # v1.4: Async function
        if tok.type == TokenType.ASYNC:
            return self._parse_async_function()

        # v1.4: Await as statement
        if tok.type == TokenType.AWAIT:
            return self._parse_await_statement()

        # v1.4: Super call as statement
        if tok.type == TokenType.SUPER:
            return self._parse_super_call()

        # v4.0: Interface definition
        if tok.type == TokenType.INTERFACE:
            return self._parse_interface_def()

        # v4.0: Module definition
        if tok.type == TokenType.MODULE:
            return self._parse_module_def()

        # v4.0: Export statement
        if tok.type == TokenType.EXPORT:
            return self._parse_export()

        # v4.0: Visibility modifiers
        if tok.type in (TokenType.PUBLIC, TokenType.PRIVATE, TokenType.PROTECTED):
            return self._parse_visibility_modifier()

        # v4.0: Static method
        if tok.type == TokenType.STATIC:
            return self._parse_static_method()

        # v4.0: Abstract method
        if tok.type == TokenType.ABSTRACT:
            return self._parse_abstract_method()

        # v4.0: Yields (generator)
        if tok.type == TokenType.YIELDS:
            return self._parse_yield()

        # v4.0: Override marker
        if tok.type == TokenType.OVERRIDE:
            return self._parse_override_method()

        # v5.1: Spawn task
        if tok.type == TokenType.SPAWN:
            return self._parse_spawn()

        # v5.1: Parallel For Each
        if tok.type == TokenType.PARALLEL:
            return self._parse_parallel_for_each()

        # v5.1: Breakpoint
        if tok.type == TokenType.BREAKPOINT_KW:
            return self._parse_breakpoint_stmt()

        # v5.2: External function (C FFI)
        if tok.type == TokenType.EXTERNAL:
            return self._parse_external_function()

        # v5.2: Load library (C FFI) — "Load" is not a keyword, it's an identifier
        if tok.type == TokenType.IDENTIFIER and tok.value.lower() == 'load':
            nxt = self._peek()
            if nxt and nxt.type == TokenType.LIBRARY:
                return self._parse_load_library()

        # v6.0: Style & Layout System
        if tok.type == TokenType.STYLE:
            return self._parse_style_def()

        if tok.type == TokenType.STYLESHEET:
            return self._parse_stylesheet_def()

        if tok.type == TokenType.HEAD:
            return self._parse_head_def()

        if tok.type == TokenType.COMPONENT:
            return self._parse_component_def()

        if tok.type == TokenType.DIV:
            return self._parse_styled_element('div')

        if tok.type == TokenType.SECTION:
            return self._parse_styled_element('section')

        if tok.type == TokenType.NAV:
            return self._parse_styled_element('nav')

        if tok.type == TokenType.HEADER_EL:
            return self._parse_styled_element('header')

        if tok.type == TokenType.FOOTER_EL:
            return self._parse_styled_element('footer')

        if tok.type == TokenType.SPAN:
            return self._parse_styled_element('span')

        if tok.type == TokenType.ARTICLE:
            return self._parse_styled_element('article')

        if tok.type == TokenType.ASIDE:
            return self._parse_styled_element('aside')

        if tok.type == TokenType.MAIN_EL:
            return self._parse_styled_element('main')

        if tok.type == TokenType.CONTAINER:
            return self._parse_styled_element('container')

        if tok.type == TokenType.FLEX:
            return self._parse_layout_container('flex')

        if tok.type == TokenType.GRID:
            return self._parse_layout_container('grid')

        if tok.type == TokenType.RESPONSIVE:
            return self._parse_responsive_block()

        if tok.type == TokenType.ANIMATE:
            return self._parse_animate_def()

        if tok.type == TokenType.TRANSITION_KW:
            return self._parse_transition_def()

        # v6.1: 3D & Canvas
        if tok.type == TokenType.SCENE:
            return self._parse_scene_3d()

        if tok.type == TokenType.DRAW:
            return self._parse_draw_command()

        # Create WebApp called myApp (special Create handling)
        if tok.type == TokenType.CREATE or tok.type == TokenType.REMEMBER:
            # Check if next token is WEBAPP
            nxt = self._peek()
            if nxt and nxt.type == TokenType.WEBAPP:
                return self._parse_webapp()
            return self._parse_var_declaration()

        # Shorthand: identifier = value (e.g., "age = 20")
        # Also handles: obj.prop = value, items[i] = value
        if self._match_identifier():
            return self._parse_shorthand_assignment()

        # v7.8: Smart keyword suggestion for misspelled words
        import difflib

        _statement_keywords = [
            'Create',
            'Make',
            'Let',
            'Set',
            'Print',
            'Display',
            'Show',
            'Say',
            'Output',
            'If',
            'While',
            'For',
            'Repeat',
            'Define',
            'Declare',
            'Function',
            'Class',
            'Return',
            'Call',
            'Try',
            'Catch',
            'Match',
            'When',
            'Import',
            'Use',
            'Write',
            'Read',
            'Append',
            'Break',
            'Continue',
            'Throw',
            'Assert',
            'Wait',
            'Exit',
            'Constant',
            'Increase',
            'Decrease',
            'Add',
            'Sort',
            'Reverse',
            'Route',
            'Start',
            'Page',
            'Send',
            'Window',
            'Async',
            'Otherwise',
            'Else',
            'End',
            'Remember',
            'Multiply',
            'Divide',
        ]
        suggestions = difflib.get_close_matches(tok.value, _statement_keywords, n=2, cutoff=0.6)
        if suggestions:
            hint = ' or '.join(f'"{s}"' for s in suggestions)
            raise ParserError(
                f'Unknown keyword "{tok.value}". Did you mean {hint}?',
                tok.line,
            )
        raise ParserError(
            f'Unexpected token "{tok.value}". Expected a statement like Create, Set, Print, If, etc.',
            tok.line,
        )

    # ─── Shorthand Assignment: "age = 20" ─────────────────

    def _parse_shorthand_assignment(self):
        """
        Handles:
          age = 20
          obj.property = value
          obj.method(args)  (as statement)
          items[i] = value  (index set)
          funcName(args)    (function call as statement)
        """
        line = self._current().line
        name_tok = self._expect_identifier()
        var_name = name_tok.value

        # Check for index access: items[i] = value
        if self._match(TokenType.LBRACKET):
            self._advance()  # consume [
            index_expr = self._parse_expression()
            self._expect(TokenType.RBRACKET, 'Expected "]".')
            if self._match(TokenType.OP_ASSIGN):
                self._advance()  # consume =
                value = self._parse_expression()
                self._end_statement()
                return ast.IndexSet(ast.Identifier(var_name, line), index_expr, value, line)
            # items[i] as expression statement
            self._end_statement()
            return ast.IndexAccess(ast.Identifier(var_name, line), index_expr, line)

        # Check for dot notation: obj.something
        if self._match(TokenType.DOT):
            self._advance()  # consume .
            prop_tok = self._expect_identifier('Expected property or method name after ".".')
            prop_name = prop_tok.value

            # obj.method(args) as statement
            if self._match(TokenType.LPAREN):
                self._advance()  # consume (
                args = []
                if not self._match(TokenType.RPAREN):
                    args.append(self._parse_expression())
                    while self._match(TokenType.COMMA):
                        self._advance()
                        args.append(self._parse_expression())
                self._expect(TokenType.RPAREN, 'Expected ")" after method arguments.')
                self._end_statement()
                return ast.MethodCall(ast.Identifier(var_name, line), prop_name, args, line)

            # obj.property = value
            if self._match(TokenType.OP_ASSIGN):
                self._advance()  # consume =
                value = self._parse_expression()
                self._end_statement()
                return ast.PropertySet(ast.Identifier(var_name, line), prop_name, value, line)

            # obj.property (just a property read — treat as expression statement)
            self._end_statement()
            return ast.PropertyAccess(ast.Identifier(var_name, line), prop_name, line)

        # Check for module access: Module::member
        if self._match(TokenType.DOUBLE_COLON):
            self._advance()  # consume ::
            member_tok = self._expect_identifier('Expected member name after "::".')
            member_name = member_tok.value
            if self._match(TokenType.LPAREN):
                self._advance()
                args = []
                if not self._match(TokenType.RPAREN):
                    args.append(self._parse_expression())
                    while self._match(TokenType.COMMA):
                        self._advance()
                        args.append(self._parse_expression())
                self._expect(TokenType.RPAREN, 'Expected ")" after arguments.')
                self._end_statement()
                return ast.ModuleAccess(var_name, member_name, args, line)
            self._end_statement()
            return ast.ModuleAccess(var_name, member_name, None, line)

        # funcName(args) — parentheses function call as statement
        if self._match(TokenType.LPAREN):
            self._advance()  # consume (
            args = []
            if not self._match(TokenType.RPAREN):
                args.append(self._parse_expression())
                while self._match(TokenType.COMMA):
                    self._advance()
                    args.append(self._parse_expression())
            self._expect(TokenType.RPAREN, 'Expected ")".')
            self._end_statement()
            return ast.FunctionCall(var_name, args, line)

        if self._match(TokenType.OP_ASSIGN):
            self._advance()  # consume =
            value = self._parse_expression()
            self._end_statement()
            return ast.VarDeclaration(var_name, value, None, line)

        # v0.6: Augmented assignment: x += 1, x -= 1, etc.
        aug_ops = {
            TokenType.OP_PLUS_ASSIGN: '+=',
            TokenType.OP_MINUS_ASSIGN: '-=',
            TokenType.OP_MUL_ASSIGN: '*=',
            TokenType.OP_DIV_ASSIGN: '/=',
            TokenType.OP_MOD_ASSIGN: '%=',
        }
        if self._current().type in aug_ops:
            op = aug_ops[self._current().type]
            self._advance()  # consume operator
            value = self._parse_expression()
            self._end_statement()
            return ast.AugmentedAssignment(var_name, op, value, line)

        # v7.8: Smart keyword suggestion for misspelled words
        import difflib

        _statement_keywords = [
            'Create',
            'Make',
            'Let',
            'Set',
            'Print',
            'Display',
            'Show',
            'Say',
            'Output',
            'If',
            'While',
            'For',
            'Repeat',
            'Define',
            'Declare',
            'Function',
            'Class',
            'Return',
            'Call',
            'Try',
            'Catch',
            'Match',
            'When',
            'Import',
            'Use',
            'Write',
            'Read',
            'Append',
            'Break',
            'Continue',
            'Throw',
            'Assert',
            'Wait',
            'Exit',
            'Constant',
            'Increase',
            'Decrease',
            'Add',
            'Sort',
            'Reverse',
            'Route',
            'Start',
            'Page',
            'Send',
            'Window',
            'Async',
            'Otherwise',
            'Else',
            'End',
            'Remember',
            'Multiply',
            'Divide',
        ]
        suggestions = difflib.get_close_matches(var_name, _statement_keywords, n=2, cutoff=0.6)
        if suggestions:
            hint = ' or '.join(f'"{s}"' for s in suggestions)
            raise ParserError(
                f'Unknown word "{var_name}". Did you mean {hint}?',
                self._current().line,
            )
        raise ParserError(
            f'Unexpected token after "{var_name}". Did you mean "{var_name} = ..."?',
            self._current().line,
        )

    # ─── Variable Declaration ─────────────────────────────

    def _parse_var_declaration(self):
        """
        Formats:
          Create age equal to 20
          Create integer named age equal to 20
          Create age = 20
        """
        line = self._current().line
        self._advance()  # consume CREATE

        # Optional article
        self._optional(TokenType.A, TokenType.AN, TokenType.THE)

        # Try to parse type
        var_type = None
        if self._match(
            TokenType.TYPE_INTEGER,
            TokenType.TYPE_DECIMAL,
            TokenType.TYPE_TEXT,
            TokenType.TYPE_BOOLEAN,
            TokenType.TYPE_LIST,
        ):
            var_type = self._advance().value.lower()

        # Skip optional "variable" keyword
        self._optional(TokenType.VARIABLE)

        # Skip optional "named" or "called" (v7.8: synonym support)
        self._optional(TokenType.NAMED, TokenType.CALLED)

        # Variable name
        name_tok = self._expect_identifier('Expected a variable name after "Create".')
        var_name = name_tok.value

        # "equal to" or "=" or "equal" or "as" (v0.7)
        if self._match(TokenType.EQUAL):
            self._advance()
            self._optional(TokenType.TO)
        elif self._match(TokenType.OP_ASSIGN):
            self._advance()
        elif self._match(TokenType.IS_EQUAL_TO):
            self._advance()
        elif self._match(TokenType.AS):
            self._advance()
        else:
            raise ParserError(
                f'Expected "equal to", "as", or "=" after variable name "{var_name}".',
                self._current().line,
            )

        value = self._parse_expression()
        self._end_statement()

        return ast.VarDeclaration(var_name, value, var_type, line)

    # ─── Variable Assignment ──────────────────────────────

    def _parse_var_assignment(self):
        """Set age to 25"""
        line = self._current().line
        self._advance()  # consume SET

        name_tok = self._expect_identifier('Expected a variable name after "Set".')
        var_name = name_tok.value

        self._expect(TokenType.TO, 'Expected "to" after variable name in Set statement.')

        value = self._parse_expression()
        self._end_statement()

        return ast.VarAssignment(var_name, value, line)

    # ─── Print ────────────────────────────────────────────

    def _parse_print(self):
        """Print "Hello"  /  Print age"""
        line = self._current().line
        self._advance()  # consume PRINT/DISPLAY/SHOW

        expr = self._parse_expression()
        self._end_statement()

        return ast.PrintStatement(expr, line)

    # ─── Input ────────────────────────────────────────────

    def _parse_input(self):
        """Input age  /  Input age with prompt "Enter: " """
        line = self._current().line
        self._advance()  # consume INPUT

        name_tok = self._expect_identifier('Expected a variable name after "Input".')
        var_name = name_tok.value

        prompt = None
        if self._match(TokenType.WITH):
            self._advance()
            if (
                self._current().type == TokenType.IDENTIFIER
                and self._current().value.lower() == 'prompt'
            ):
                self._advance()
            prompt_tok = self._expect(TokenType.STRING, 'Expected a prompt string after "with".')
            prompt = prompt_tok.value

        self._end_statement()

        return ast.InputStatement(var_name, prompt, line)

    # ─── Ask (English alias for Input) ────────────────────

    def _parse_ask(self):
        """Ask "What is your name?" and store in name"""
        line = self._current().line
        self._advance()  # consume ASK

        prompt = None
        if self._match(TokenType.STRING):
            prompt = self._current().value
            self._advance()

        # Expect "and store in" or "store in" or "in"
        if self._match(TokenType.AND):
            self._advance()
        if self._match(TokenType.STORE):
            self._advance()
        self._optional(TokenType.IN)

        name_tok = self._expect_identifier('Expected a variable name after Ask.')
        var_name = name_tok.value

        self._end_statement()
        return ast.InputStatement(var_name, prompt, line)

    # ─── If Statement ─────────────────────────────────────

    def _parse_if(self):
        """
        If age > 18 then
            Print "Adult"
        Otherwise
            Print "Minor"
        End
        """
        line = self._current().line
        self._advance()  # consume IF

        condition = self._parse_expression()

        # Optional "then"
        self._optional(TokenType.THEN)
        self._skip_newlines()

        # Parse then-body until Otherwise or End
        then_body = []
        while not self._is_block_end():
            stmt = self._parse_statement()
            if stmt:
                then_body.append(stmt)
            self._skip_newlines()

        # Optional otherwise-body (supports "Otherwise if" chaining)
        else_body = []
        if self._match(TokenType.OTHERWISE):
            self._advance()

            # v0.3: "Otherwise if" — chains into nested IfStatement
            if self._match(TokenType.IF):
                nested_if = self._parse_if()
                else_body = [nested_if]
            else:
                self._skip_newlines()
                while not self._match(TokenType.END, TokenType.END_IF, TokenType.EOF):
                    stmt = self._parse_statement()
                    if stmt:
                        else_body.append(stmt)
                    self._skip_newlines()
                self._consume_block_end()
                return ast.IfStatement(condition, then_body, else_body, line)

        if not else_body or not (len(else_body) == 1 and isinstance(else_body[0], ast.IfStatement)):
            self._consume_block_end()

        return ast.IfStatement(condition, then_body, else_body, line)

    # ─── While Loop ───────────────────────────────────────

    def _parse_while(self):
        """While count < 10 ... End"""
        line = self._current().line
        self._advance()  # consume WHILE

        condition = self._parse_expression()
        self._skip_newlines()

        body = []
        while not self._match(TokenType.END, TokenType.END_WHILE, TokenType.EOF):
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
            self._skip_newlines()

        self._consume_block_end()

        return ast.WhileLoop(condition, body, line)

    # ─── Repeat Loop ──────────────────────────────────────

    def _parse_repeat(self):
        """Repeat 5 times ... End"""
        line = self._current().line
        self._advance()  # consume REPEAT

        count = self._parse_expression()

        self._expect(TokenType.TIMES, 'Expected "times" after repeat count.')
        self._skip_newlines()

        body = []
        while not self._match(TokenType.END, TokenType.END_REPEAT, TokenType.EOF):
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
            self._skip_newlines()

        self._consume_block_end()

        return ast.RepeatLoop(count, body, line)

    # ─── For Each Loop ────────────────────────────────────

    def _parse_for(self):
        """For each item in list ... End  OR  For i from 1 to 10 ... End"""
        line = self._current().line
        self._advance()  # consume FOR

        # Check if it's "For each" (for-each loop) or "For var from" (for-range loop)
        if self._match(TokenType.EACH):
            return self._parse_for_each_body(line)
        else:
            return self._parse_for_range_body(line)

    def _parse_for_each_body(self, line):
        """For each item in myList ... End"""
        self._advance()  # consume EACH

        var_tok = self._expect_identifier('Expected a variable name after "For each".')
        var_name = var_tok.value

        self._expect(TokenType.IN, 'Expected "in" after variable name in For each loop.')

        iterable = self._parse_expression()
        self._skip_newlines()

        body = []
        while not self._match(TokenType.END, TokenType.END_FOR, TokenType.EOF):
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
            self._skip_newlines()

        self._consume_block_end()

        return ast.ForEachLoop(var_name, iterable, body, line)

    def _parse_for_range_body(self, line):
        """For i from 1 to 10 ... End  OR  For i from 1 to 10 step 2 ... End"""
        var_tok = self._expect_identifier('Expected variable name after "For".')
        var_name = var_tok.value

        self._expect(TokenType.FROM, 'Expected "from" after variable name in For loop.')
        start = self._parse_expression()

        self._expect(TokenType.TO, 'Expected "to" after start value in For loop.')
        end = self._parse_expression()

        # v0.6: optional step
        step = None
        if self._match(TokenType.STEP):
            self._advance()  # consume STEP
            step = self._parse_expression()

        self._skip_newlines()

        body = []
        while not self._match(TokenType.END, TokenType.END_FOR, TokenType.EOF):
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
            self._skip_newlines()

        self._consume_block_end()

        return ast.ForRange(var_name, start, end, body, line, step)

    # ─── Function Definition (Full) ───────────────────────

    def _parse_function_def(self):
        """
        Define a function named greet that takes text personName and returns nothing
            Print "Hello"
        End
        """
        line = self._current().line
        self._advance()  # consume DEFINE

        self._optional(TokenType.A, TokenType.AN, TokenType.THE)
        self._expect(TokenType.FUNCTION, 'Expected "function" after "Define".')
        self._optional(TokenType.NAMED)

        name_tok = self._expect_identifier('Expected function name.')
        func_name = name_tok.value

        params = []
        if self._match(TokenType.THAT):
            self._advance()
            self._expect(TokenType.TAKES, 'Expected "takes" after "that".')
            params = self._parse_param_list()
        elif self._match(TokenType.TAKES, TokenType.WITH):
            self._advance()
            params = self._parse_param_list()
        elif self._match(TokenType.LPAREN):
            self._advance()
            if not self._match(TokenType.RPAREN):
                params = self._parse_param_list()
            self._expect(TokenType.RPAREN, 'Expected ")" after function parameters.')

        return_type = None
        if self._match(TokenType.AND):
            self._advance()
            self._expect(TokenType.RETURNS, 'Expected "returns" after "and".')
            if self._match(
                TokenType.TYPE_INTEGER,
                TokenType.TYPE_DECIMAL,
                TokenType.TYPE_TEXT,
                TokenType.TYPE_BOOLEAN,
                TokenType.TYPE_LIST,
                TokenType.NOTHING,
            ):
                return_type = self._advance().value.lower()

        self._end_statement()
        self._skip_newlines()

        body = []
        while not self._match(TokenType.END, TokenType.END_FUNCTION, TokenType.EOF):
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
            self._skip_newlines()

        self._consume_block_end()

        return ast.FunctionDef(func_name, params, return_type, body, line)

    # ─── Function Definition (Short: "Function add takes a and b") ────

    def _parse_function_def_short(self):
        """
        Function greet takes name
            Print "Hello, " + name
        End
        """
        line = self._current().line
        self._advance()  # consume FUNCTION

        name_tok = self._expect_identifier('Expected function name.')
        func_name = name_tok.value

        params = []
        if self._match(TokenType.TAKES, TokenType.WITH):
            self._advance()
            params = self._parse_param_list()
        elif self._match(TokenType.LPAREN):
            self._advance()
            if not self._match(TokenType.RPAREN):
                params = self._parse_param_list()
            self._expect(TokenType.RPAREN, 'Expected ")" after function parameters.')

        return_type = None
        if self._match(TokenType.AND):
            self._advance()
            self._expect(TokenType.RETURNS, 'Expected "returns" after "and".')
            if self._match(
                TokenType.TYPE_INTEGER,
                TokenType.TYPE_DECIMAL,
                TokenType.TYPE_TEXT,
                TokenType.TYPE_BOOLEAN,
                TokenType.TYPE_LIST,
                TokenType.NOTHING,
            ):
                return_type = self._advance().value.lower()

        self._end_statement()
        self._skip_newlines()

        body = []
        while not self._match(TokenType.END, TokenType.END_FUNCTION, TokenType.EOF):
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
            self._skip_newlines()

        self._consume_block_end()

        return ast.FunctionDef(func_name, params, return_type, body, line)

    def _parse_param_list(self) -> list:
        """Parse function parameters: integer a and text b  OR  a, b = 10"""
        params: list = []  # holds (name, type, default) tuples and RestParameter nodes
        has_default = False

        # "takes nothing" means no parameters
        if self._match(TokenType.NOTHING):
            # Only consume if followed by AND/RETURNS/newline/End (not another identifier)
            nxt = self._peek()
            if nxt and nxt.type in (
                TokenType.AND,
                TokenType.RETURNS,
                TokenType.NEWLINE,
                TokenType.END,
                TokenType.EOF,
                TokenType.DOT,
            ):
                self._advance()  # consume "nothing"
                return params

        while True:
            # Check for rest parameter: "rest items"
            if self._match(TokenType.REST):
                self._advance()  # consume "rest"
                if not self._match_identifier():
                    raise ParserError('Expected parameter name after "rest".', self._current().line)
                rest_name = self._expect_identifier('Expected rest parameter name.').value
                params.append(ast.RestParameter(rest_name, self._current().line))
                break  # rest must be last

            param_type = None
            if self._match(
                TokenType.TYPE_INTEGER,
                TokenType.TYPE_DECIMAL,
                TokenType.TYPE_TEXT,
                TokenType.TYPE_BOOLEAN,
                TokenType.TYPE_LIST,
            ):
                param_type = self._advance().value.lower()

            if not self._match_identifier():
                break
            param_name = self._expect_identifier('Expected parameter name.').value

            # Check for default value: param = expr
            default_expr = None
            if self._match(TokenType.OP_ASSIGN):
                self._advance()  # consume =
                default_expr = self._parse_expression()
                has_default = True
            elif has_default:
                raise ParserError(
                    f'Parameter "{param_name}" must have a default value (parameters with defaults must come last).',
                    self._current().line,
                )

            params.append((param_name, param_type, default_expr))

            if self._match(TokenType.AND):
                if self._peek().type == TokenType.RETURNS:
                    break
                self._advance()
            elif self._match(TokenType.COMMA):
                self._advance()
            else:
                break

        return params

    # ─── Call Statement ───────────────────────────────────

    def _parse_call_statement(self):
        """Call greet with "Abneesh" """
        call_expr = self._parse_call_expression()
        self._end_statement()
        return call_expr

    def _parse_call_expression(self):
        """Parse function call: call add with 5 and 10"""
        line = self._current().line
        self._advance()  # consume CALL

        callee = self._parse_postfix()

        arguments = []
        if self._match(TokenType.WITH):
            self._advance()
            arguments = self._parse_arg_list()

        if isinstance(callee, ast.FunctionCall):
            return callee

        if isinstance(callee, ast.MethodCall):
            return callee

        if isinstance(callee, ast.Identifier):
            return ast.FunctionCall(callee.name, arguments, line)

        if isinstance(callee, ast.PropertyAccess):
            return ast.MethodCall(callee.obj, callee.property_name, arguments, line)

        if isinstance(callee, ast.ModuleAccess):
            if callee.arguments is None:
                return ast.ModuleAccess(callee.module_name, callee.member_name, arguments, line)
            return callee

        raise ParserError('Expected function or method name after "Call".', line)

    def _parse_arg_list(self) -> list:
        """Parse function arguments: 5 and 10"""
        args = []
        args.append(self._parse_comparison())

        while self._match(TokenType.AND, TokenType.COMMA):
            self._advance()
            args.append(self._parse_comparison())

        return args

    # ─── Return ───────────────────────────────────────────

    def _parse_return(self):
        """Return result"""
        line = self._current().line
        self._advance()  # consume RETURN

        value = None
        if not self._match(TokenType.DOT, TokenType.NEWLINE, TokenType.EOF):
            value = self._parse_expression()

        self._end_statement()

        return ast.ReturnStatement(value, line)

    # ─── Increase / Decrease ──────────────────────────────

    def _parse_increase(self):
        """Increase age by 1"""
        line = self._current().line
        self._advance()

        name_tok = self._expect_identifier('Expected variable name after "Increase".')
        var_name = name_tok.value

        self._expect(TokenType.BY, 'Expected "by" after variable name.')

        amount = self._parse_expression()
        self._end_statement()

        return ast.VarAssignment(
            var_name, ast.BinaryOp(ast.Identifier(var_name, line), '+', amount, line), line
        )

    def _parse_decrease(self):
        """Decrease age by 1"""
        line = self._current().line
        self._advance()

        name_tok = self._expect_identifier('Expected variable name after "Decrease".')
        var_name = name_tok.value

        self._expect(TokenType.BY, 'Expected "by" after variable name.')

        amount = self._parse_expression()
        self._end_statement()

        return ast.VarAssignment(
            var_name, ast.BinaryOp(ast.Identifier(var_name, line), '-', amount, line), line
        )

    def _parse_multiply_by(self):
        """Multiply score by 2"""
        line = self._current().line
        self._advance()

        name_tok = self._expect_identifier('Expected variable name after "Multiply".')
        var_name = name_tok.value

        self._expect(TokenType.BY, 'Expected "by" after variable name.')

        amount = self._parse_expression()
        self._end_statement()

        return ast.VarAssignment(
            var_name, ast.BinaryOp(ast.Identifier(var_name, line), '*', amount, line), line
        )

    def _parse_divide_by(self):
        """Divide total by 4"""
        line = self._current().line
        self._advance()

        name_tok = self._expect_identifier('Expected variable name after "Divide".')
        var_name = name_tok.value

        self._expect(TokenType.BY, 'Expected "by" after variable name.')

        amount = self._parse_expression()
        self._end_statement()

        return ast.VarAssignment(
            var_name, ast.BinaryOp(ast.Identifier(var_name, line), '/', amount, line), line
        )

    # ─── Expression Parsing ───────────────────────────────

    def _parse_expression(self):
        self._depth += 1
        if self._depth > self.MAX_DEPTH:
            raise ParserError(
                'Expression nesting too deep (maximum 200 levels). '
                'Break complex expressions into smaller variables or functions.',
                self._current().line,
            )
        try:
            expr = self._parse_or()
            # v0.6: Ternary expression: expr if condition otherwise other
            if self._match(TokenType.IF):
                self._advance()  # consume IF
                condition = self._parse_or()
                self._expect(TokenType.OTHERWISE, 'Expected "otherwise" in ternary expression.')
                false_expr = self._parse_or()
                return ast.TernaryExpression(expr, condition, false_expr, getattr(expr, 'line', 0))
            return expr
        finally:
            self._depth -= 1

    def _parse_or(self):
        left = self._parse_and()
        while self._match(TokenType.OR):
            self._advance()
            right = self._parse_and()
            left = ast.BinaryOp(left, 'or', right, getattr(left, 'line', 0))
        return left

    def _parse_and(self):
        left = self._parse_comparison()
        while self._match(TokenType.AND):
            self._advance()
            right = self._parse_comparison()
            left = ast.BinaryOp(left, 'and', right, getattr(left, 'line', 0))
        return left

    def _parse_comparison(self):
        left = self._parse_addition()

        comparison_ops = {
            TokenType.OP_GREATER: '>',
            TokenType.OP_LESS: '<',
            TokenType.OP_EQUAL: '==',
            TokenType.OP_NOT_EQUAL: '!=',
            TokenType.OP_GREATER_EQ: '>=',
            TokenType.OP_LESS_EQ: '<=',
            TokenType.IS_GREATER_THAN: '>',
            TokenType.IS_LESS_THAN: '<',
            TokenType.IS_EQUAL_TO: '==',
            TokenType.IS_NOT_EQUAL_TO: '!=',
            TokenType.IS_GREATER_THAN_OR_EQUAL_TO: '>=',
            TokenType.IS_LESS_THAN_OR_EQUAL_TO: '<=',
            # v0.7.1: Simplified comparison phrases
            TokenType.EQUALS_KW: '==',
            TokenType.NOT_EQUALS: '!=',
            TokenType.DOES_NOT_EQUAL: '!=',
            TokenType.AT_LEAST: '>=',
            TokenType.AT_MOST: '<=',
        }

        if self._current().type in comparison_ops:
            op = comparison_ops[self._current().type]
            self._advance()
            right = self._parse_addition()
            left = ast.BinaryOp(left, op, right, getattr(left, 'line', 0))

        # v0.7: "is between X and Y" → left >= X and left <= Y
        # Handle both "between" and "is between" patterns
        _is_between = False
        if self._match(TokenType.BETWEEN):
            _is_between = True
        elif self._match(TokenType.IS):
            if self._peek() and self._peek().type == TokenType.BETWEEN:
                self._advance()  # consume IS
                _is_between = True
        if _is_between:
            self._advance()  # consume BETWEEN
            low = self._parse_addition()
            self._expect(TokenType.AND, 'Expected "and" in "is between X and Y".')
            high = self._parse_addition()
            line = getattr(left, 'line', 0)
            left = ast.BinaryOp(
                ast.BinaryOp(left, '>=', low, line),
                'and',
                ast.BinaryOp(left, '<=', high, line),
                line,
            )

        return left

    def _parse_addition(self):
        left = self._parse_multiplication()

        while self._match(TokenType.OP_PLUS, TokenType.OP_MINUS, TokenType.PLUS, TokenType.MINUS):
            tok = self._advance()
            if tok.type in (TokenType.OP_PLUS, TokenType.PLUS):
                op = '+'
            else:
                op = '-'
            right = self._parse_multiplication()
            left = ast.BinaryOp(left, op, right, getattr(left, 'line', 0))

        return left

    def _parse_multiplication(self):
        left = self._parse_power()

        while self._match(
            TokenType.OP_MULTIPLY,
            TokenType.OP_DIVIDE,
            TokenType.OP_MODULO,
            TokenType.OP_FLOOR_DIV,
            TokenType.MOD_KW,
        ):
            tok = self._advance()
            if tok.type == TokenType.OP_MULTIPLY:
                op = '*'
            elif tok.type == TokenType.OP_DIVIDE:
                op = '/'
            elif tok.type == TokenType.OP_FLOOR_DIV:
                op = '//'
            else:
                op = '%'
            right = self._parse_power()
            left = ast.BinaryOp(left, op, right, getattr(left, 'line', 0))

        return left

    def _parse_power(self):
        """Power operator ** (right-associative)"""
        base = self._parse_unary()
        if self._match(TokenType.OP_POWER):
            self._advance()
            exponent = self._parse_power()  # right-associative via recursion
            return ast.BinaryOp(base, '**', exponent, getattr(base, 'line', 0))
        return base

    def _parse_unary(self):
        if self._match(TokenType.NOT):
            self._advance()
            operand = self._parse_unary()
            return ast.UnaryOp('not', operand)

        if self._match(TokenType.OP_MINUS):
            self._advance()
            operand = self._parse_unary()
            return ast.UnaryOp('-', operand)

        return self._parse_postfix()

    def _parse_postfix(self):
        """Parse postfix: dot notation (obj.prop, obj.method()) and index access (items[i])."""
        expr = self._parse_primary()

        while True:
            if self._match(TokenType.DOT):
                # Peek ahead: is this dot notation or a period?
                next_tok = self._peek()
                if (
                    next_tok.type != TokenType.IDENTIFIER
                    and next_tok.type not in self._SOFT_KEYWORDS
                ):
                    break  # It's a period, don't consume

                self._advance()  # consume .
                prop_tok = self._expect_identifier('Expected property or method name after ".".')
                prop_name = prop_tok.value

                # Check for method call: obj.method(args)
                if self._match(TokenType.LPAREN):
                    self._advance()  # consume (
                    args = []
                    if not self._match(TokenType.RPAREN):
                        args.append(self._parse_expression())
                        while self._match(TokenType.COMMA):
                            self._advance()
                            args.append(self._parse_expression())
                    self._expect(TokenType.RPAREN, 'Expected ")" after method arguments.')
                    expr = ast.MethodCall(expr, prop_name, args, getattr(expr, 'line', 0))
                else:
                    # Property access: obj.prop
                    expr = ast.PropertyAccess(expr, prop_name, getattr(expr, 'line', 0))

            elif self._match(TokenType.DOUBLE_COLON):
                # Module access: Module::member or Module::func(args)
                self._advance()  # consume ::
                member_tok = self._expect_identifier('Expected member name after "::".')
                member_name = member_tok.value
                mod_name = getattr(expr, 'name', str(expr))
                line = getattr(expr, 'line', 0)
                if self._match(TokenType.LPAREN):
                    self._advance()
                    args = []
                    if not self._match(TokenType.RPAREN):
                        args.append(self._parse_expression())
                        while self._match(TokenType.COMMA):
                            self._advance()
                            args.append(self._parse_expression())
                    self._expect(TokenType.RPAREN, 'Expected ")" after arguments.')
                    expr = ast.ModuleAccess(mod_name, member_name, args, line)
                else:
                    expr = ast.ModuleAccess(mod_name, member_name, None, line)

            elif self._match(TokenType.LBRACKET):
                # Index access: items[i]  OR  Slice: items[start:end] or items[start:end:step]
                self._advance()  # consume [
                # Check for slice: [:end]
                if self._match(TokenType.COLON):
                    start_expr = ast.Literal(None, getattr(expr, 'line', 0))
                    self._advance()  # consume :
                    if self._match(TokenType.RBRACKET):
                        end_expr = ast.Literal(None, getattr(expr, 'line', 0))
                        step_expr = None
                    elif self._match(TokenType.COLON):
                        end_expr = ast.Literal(None, getattr(expr, 'line', 0))
                        self._advance()  # consume :
                        step_expr = self._parse_expression()
                    else:
                        end_expr = self._parse_expression()
                        step_expr = None
                        if self._match(TokenType.COLON):
                            self._advance()
                            step_expr = self._parse_expression()
                    self._expect(TokenType.RBRACKET, 'Expected "]".')
                    expr = ast.SliceAccess(
                        expr, start_expr, end_expr, step_expr, getattr(expr, 'line', 0)
                    )
                else:
                    index_expr = self._parse_expression()
                    # Check if this is a slice
                    if self._match(TokenType.COLON):
                        self._advance()  # consume :
                        if self._match(TokenType.RBRACKET):
                            end_expr = ast.Literal(None, getattr(expr, 'line', 0))
                            step_expr = None
                        elif self._match(TokenType.COLON):
                            end_expr = ast.Literal(None, getattr(expr, 'line', 0))
                            self._advance()
                            step_expr = self._parse_expression()
                        else:
                            end_expr = self._parse_expression()
                            step_expr = None
                            if self._match(TokenType.COLON):
                                self._advance()
                                step_expr = self._parse_expression()
                        self._expect(TokenType.RBRACKET, 'Expected "]".')
                        expr = ast.SliceAccess(
                            expr, index_expr, end_expr, step_expr, getattr(expr, 'line', 0)
                        )
                    else:
                        self._expect(TokenType.RBRACKET, 'Expected "]".')
                        expr = ast.IndexAccess(expr, index_expr, getattr(expr, 'line', 0))
            else:
                break

        return expr

    def _parse_primary(self):
        tok = self._current()

        # v0.6: Lambda expression: lambda x, y -> x + y
        # v0.7.1: Also supports: given x, y return x + y
        if tok.type == TokenType.LAMBDA:
            return self._parse_lambda()

        if tok.type == TokenType.GIVEN:
            # Peek ahead: only treat as lambda if followed by identifier, RETURN, or ARROW
            nxt = self._peek()
            if nxt and (
                nxt.type == TokenType.RETURN
                or nxt.type == TokenType.ARROW
                or nxt.type == TokenType.IDENTIFIER
                or nxt.type in self._SOFT_KEYWORDS
            ):
                return self._parse_given()

        if tok.type == TokenType.NUMBER:
            self._advance()
            return ast.Literal(tok.value, tok.line)

        if tok.type == TokenType.STRING:
            self._advance()
            return ast.Literal(tok.value, tok.line)

        if tok.type == TokenType.BOOLEAN_TRUE:
            self._advance()
            return ast.Literal(True, tok.line)

        if tok.type == TokenType.BOOLEAN_FALSE:
            self._advance()
            return ast.Literal(False, tok.line)

        if tok.type == TokenType.NOTHING:
            self._advance()
            return ast.Literal(None, tok.line)

        if tok.type == TokenType.CALL:
            return self._parse_call_expression()

        # v0.3: Map expression
        if tok.type == TokenType.MAP:
            return self._parse_map_literal()

        # v0.2: "new ClassName" — create instance
        if tok.type == TokenType.NEW:
            return self._parse_new_instance()

        # v0.2: "Read file" expression
        if tok.type == TokenType.READ:
            return self._parse_read_expression()

        if tok.type == TokenType.LBRACKET:
            return self._parse_list_literal()

        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN, 'Expected closing parenthesis ")".')
            return expr

        # v0.2: "this" keyword for class methods
        if tok.type == TokenType.THIS:
            self._advance()
            return ast.Identifier('this', tok.line)

        # v1.4: Await as expression: Await func()
        if tok.type == TokenType.AWAIT:
            self._advance()
            expr = self._parse_expression()
            return ast.AwaitExpression(expr, tok.line)

        # v1.4: Super as expression: Super.method(args)
        if tok.type == TokenType.SUPER:
            self._advance()
            if self._match(TokenType.DOT):
                self._advance()
                method_tok = self._expect_identifier('Expected method name after "Super.".')
                method_name = method_tok.value
                arguments = []
                if self._match(TokenType.LPAREN):
                    self._advance()
                    if not self._match(TokenType.RPAREN):
                        arguments.append(self._parse_expression())
                        while self._match(TokenType.COMMA):
                            self._advance()
                            arguments.append(self._parse_expression())
                    self._expect(TokenType.RPAREN, 'Expected ")" after super arguments.')
                return ast.SuperCall(method_name, arguments, tok.line)
            elif self._match(TokenType.LPAREN):
                self._advance()
                arguments = []
                if not self._match(TokenType.RPAREN):
                    arguments.append(self._parse_expression())
                    while self._match(TokenType.COMMA):
                        self._advance()
                        arguments.append(self._parse_expression())
                self._expect(TokenType.RPAREN, 'Expected ")" after super arguments.')
                return ast.SuperCall(None, arguments, tok.line)
            return ast.SuperCall(None, [], tok.line)

        # Identifier (variable reference) — also accept soft keywords
        if tok.type == TokenType.IDENTIFIER or tok.type in self._SOFT_KEYWORDS:
            self._advance()
            # Check if this is a function call: funcName(args)
            if self._match(TokenType.LPAREN):
                self._advance()  # consume (
                args = []
                if not self._match(TokenType.RPAREN):
                    args.append(self._parse_expression())
                    while self._match(TokenType.COMMA):
                        self._advance()
                        args.append(self._parse_expression())
                self._expect(TokenType.RPAREN, 'Expected ")" after function arguments.')
                return ast.FunctionCall(tok.value, args, tok.line)
            return ast.Identifier(tok.value, tok.line)

        # Guidance for a common mistake: `Create x equal to Create WebApp ...`.
        # `Create WebApp` is a statement, not an expression, so it can't follow
        # "equal to". Point the user at the correct statement form.
        if tok.type == TokenType.CREATE and self._peek().type == TokenType.WEBAPP:
            raise ParserError(
                '"Create WebApp" is a statement, not a value, so it cannot be '
                'assigned with "equal to". Write it on its own line instead, '
                'naming the app directly — e.g. `Create WebApp called app`.',
                tok.line,
            )

        raise ParserError(
            f'Expected a value or expression, but found "{tok.value}" ({tok.type.name}).', tok.line
        )

    def _parse_list_literal(self):
        line = self._current().line
        self._advance()  # consume [

        elements = []
        if not self._match(TokenType.RBRACKET):
            elements.append(self._parse_expression())
            while self._match(TokenType.COMMA):
                self._advance()
                elements.append(self._parse_expression())

        self._expect(TokenType.RBRACKET, 'Expected closing bracket "]".')
        return ast.ListLiteral(elements, line)

    # ─── v0.2: File I/O ──────────────────────────────────

    def _parse_write(self):
        """Write "content" to file "path" """
        line = self._current().line
        self._advance()  # consume WRITE

        content = self._parse_expression()

        self._expect(TokenType.TO, 'Expected "to" after content in Write statement.')
        self._expect(TokenType.FILE, 'Expected "file" after "to" in Write statement.')

        filepath = self._parse_expression()
        self._end_statement()

        return ast.FileWrite(content, filepath, line)

    def _parse_append(self):
        """Append "content" to file "path" """
        line = self._current().line
        self._advance()  # consume APPEND

        content = self._parse_expression()

        self._expect(TokenType.TO, 'Expected "to" after content in Append statement.')
        self._expect(TokenType.FILE, 'Expected "file" after "to" in Append statement.')

        filepath = self._parse_expression()
        self._end_statement()

        return ast.FileAppend(content, filepath, line)

    def _parse_read_expression(self):
        """Read file "path" — as an expression that returns content."""
        line = self._current().line
        self._advance()  # consume READ

        self._expect(TokenType.FILE, 'Expected "file" after "Read".')

        filepath = self._parse_expression()

        return ast.FileRead(filepath, line)

    # ─── v0.2: Class Definition ──────────────────────────

    def _parse_class_def(self):
        """Class Animal ... End  /  Class Dog extends Animal ... End
        Class Stack<T> ... End  /  Class Pair<K, V> extends Base ... End"""
        line = self._current().line
        self._advance()  # consume CLASS

        name_tok = self._expect_identifier('Expected class name.')
        class_name = name_tok.value

        # v5.0: Optional type parameters — Class Stack<T> / Class Map<K, V>
        type_params = []
        if self._match(TokenType.OP_LESS):
            self._advance()  # consume <
            tp = self._expect_identifier('Expected type parameter name.')
            type_params.append(tp.value)
            while self._match(TokenType.COMMA):
                self._advance()
                tp = self._expect_identifier('Expected type parameter name.')
                type_params.append(tp.value)
            self._expect(TokenType.OP_GREATER, 'Expected ">" to close type parameters.')

        # v0.3: Optional inheritance
        parent_name = None
        if self._match(TokenType.EXTENDS):
            self._advance()
            parent_tok = self._expect_identifier('Expected parent class name after "extends".')
            parent_name = parent_tok.value

        # v4.0: Optional implements
        implements = []
        if self._match(TokenType.IMPLEMENTS):
            self._advance()
            iface_tok = self._expect_identifier('Expected interface name after "implements".')
            implements.append(iface_tok.value)
            while self._match(TokenType.COMMA):
                self._advance()
                iface_tok = self._expect_identifier('Expected interface name.')
                implements.append(iface_tok.value)

        self._end_statement()
        self._skip_newlines()

        body = []
        while not self._match(TokenType.END, TokenType.END_FUNCTION, TokenType.EOF):
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
            self._skip_newlines()

        self._consume_block_end()

        # Return GenericClassDef if type params present, otherwise regular ClassDef
        if type_params:
            return ast.GenericClassDef(
                class_name, type_params, body, parent=parent_name, implements=implements, line=line
            )
        return ast.ClassDef(class_name, body, parent=parent_name, implements=implements, line=line)

    def _parse_new_instance(self):
        """new ClassName"""
        line = self._current().line
        self._advance()  # consume NEW

        name_tok = self._expect_identifier('Expected class name after "new".')
        class_name = name_tok.value

        # Optional constructor arguments: new ClassName(arg1, arg2)
        arguments = []
        if self._match(TokenType.LPAREN):
            self._advance()
            if not self._match(TokenType.RPAREN):
                arguments.append(self._parse_expression())
                while self._match(TokenType.COMMA):
                    self._advance()
                    arguments.append(self._parse_expression())
            self._expect(TokenType.RPAREN, 'Expected ")" after constructor arguments.')

        return ast.NewInstance(class_name, arguments, line)

    # ─── v0.3: Try/Catch ─────────────────────────────────

    def _parse_try_catch(self):
        """Try ... Catch error ... Finally ... End"""
        line = self._current().line
        self._advance()  # consume TRY
        self._end_statement()
        self._skip_newlines()

        try_body = []
        while not self._match(TokenType.CATCH, TokenType.FINALLY, TokenType.END, TokenType.EOF):
            stmt = self._parse_statement()
            if stmt:
                try_body.append(stmt)
            self._skip_newlines()

        # Parse Catch clause (optional if Finally present)
        error_var = 'error'
        catch_body = []
        if self._match(TokenType.CATCH):
            self._advance()  # consume CATCH

            # Optional error variable name
            if self._match_identifier():
                error_var = self._expect_identifier().value

            self._end_statement()
            self._skip_newlines()

            while not self._match(TokenType.FINALLY, TokenType.END, TokenType.EOF):
                stmt = self._parse_statement()
                if stmt:
                    catch_body.append(stmt)
                self._skip_newlines()

        # Parse Finally clause (optional)
        finally_body = []
        if self._match(TokenType.FINALLY):
            self._advance()  # consume FINALLY
            self._end_statement()
            self._skip_newlines()

            while not self._match(TokenType.END, TokenType.EOF):
                stmt = self._parse_statement()
                if stmt:
                    finally_body.append(stmt)
                self._skip_newlines()

        self._consume_block_end()

        return ast.TryCatch(try_body, error_var, catch_body, finally_body, line)

    # ─── v0.3: Match/When ────────────────────────────────

    def _parse_match(self):
        """Match expr ... When "value" ... Default ... End"""
        line = self._current().line
        self._advance()  # consume MATCH

        expression = self._parse_expression()
        self._end_statement()
        self._skip_newlines()

        when_clauses = []
        default_body = []

        while not self._match(TokenType.END, TokenType.EOF):
            if self._match(TokenType.WHEN):
                self._advance()  # consume WHEN
                # Parse values: When "Monday" or "Tuesday"
                values = [self._parse_expression()]
                while self._match(TokenType.OR):
                    self._advance()
                    values.append(self._parse_expression())
                self._end_statement()
                self._skip_newlines()

                body = []
                while not self._match(
                    TokenType.WHEN, TokenType.DEFAULT, TokenType.END, TokenType.EOF
                ):
                    stmt = self._parse_statement()
                    if stmt:
                        body.append(stmt)
                    self._skip_newlines()

                when_clauses.append(ast.WhenClause(values, body, line=self._current().line))

            elif self._match(TokenType.DEFAULT):
                self._advance()  # consume DEFAULT
                self._end_statement()
                self._skip_newlines()

                while not self._match(TokenType.END, TokenType.EOF):
                    stmt = self._parse_statement()
                    if stmt:
                        default_body.append(stmt)
                    self._skip_newlines()
            else:
                break

        self._consume_block_end()

        return ast.MatchStatement(expression, when_clauses, default_body, line)

    # ─── v0.3: Map Literal ───────────────────────────────

    def _parse_map_literal(self):
        """Map with key = value and key2 = value2"""
        line = self._current().line
        self._advance()  # consume MAP

        self._expect(TokenType.WITH, 'Expected "with" after "Map".')
        # Allow the first pair to start on the next line (multi-line map literal).
        self._skip_newlines()

        pairs = []
        # Parse first pair: key = value
        key_tok = self._expect_identifier('Expected key name in Map.')
        self._expect(TokenType.OP_ASSIGN, 'Expected "=" after key name.')
        value = self._parse_comparison()  # use comparison to avoid consuming 'and'
        pairs.append((key_tok.value, value))

        # Parse remaining pairs: "and key = value". Tolerate newlines around the
        # "and" so map literals can span multiple lines, but never swallow the
        # statement-terminating newline of a single-line map: only skip newlines
        # when a continuation "and" actually follows, otherwise rewind.
        while True:
            saved = self.pos
            self._skip_newlines()
            if not self._match(TokenType.AND):
                self.pos = saved
                break
            self._advance()  # consume AND
            self._skip_newlines()  # allow "and" at end of line, key on the next
            key_tok = self._expect_identifier('Expected key name after "and".')
            self._expect(TokenType.OP_ASSIGN, 'Expected "=" after key name.')
            value = self._parse_comparison()
            pairs.append((key_tok.value, value))

        return ast.DictLiteral(pairs, line)

    # ─── v0.3: Import ────────────────────────────────────

    def _parse_import(self):
        """Import "helpers.epl"  or  Import "math" as Math"""
        line = self._current().line
        self._advance()  # consume IMPORT

        filepath_tok = self._current()
        if filepath_tok.type != TokenType.STRING:
            raise ParserError('Expected file path string after "Import".', line)
        self._advance()

        # Optional alias: Import "module" as Alias
        alias = None
        if self._current().type == TokenType.AS:
            self._advance()  # consume AS
            alias_tok = self._expect_identifier('Expected alias name after "as".')
            alias = alias_tok.value

        self._end_statement()

        return ast.ImportStatement(filepath_tok.value, line, alias=alias)

    def _parse_comment(self):
        """Comment "text" — compatibility alias for Note: comments."""
        self._advance()  # consume COMMENT
        while not self._match(TokenType.NEWLINE, TokenType.EOF, TokenType.DOT):
            self._advance()
        self._end_statement()
        return None

    # ─── v0.3: Use python library / v5.3: Use javascript ──

    def _parse_use(self):
        """Use "package" (EPL import) OR Use python "library" OR Use javascript/typescript "library\""""
        line = self._current().line
        self._advance()  # consume USE

        # Check if next token is "python" (Python library import)
        # OR a string (EPL package import - new simpler syntax)
        if self._match(TokenType.PYTHON):
            # Original behavior: Use python "library"
            self._advance()  # consume PYTHON
            lib_tok = self._current()
            if lib_tok.type != TokenType.STRING:
                raise ParserError('Expected library name string after "Use python".', line)
            self._advance()
            library = lib_tok.value

            # Optional alias
            alias = None
            if self._match(TokenType.AS):
                self._advance()
                alias_tok = self._expect_identifier('Expected alias name after "as".')
                alias = alias_tok.value
            else:
                # Use last part of module name as alias
                alias = library.split('.')[-1]

            self._end_statement()
            return ast.UseStatement(library, alias, line)

        # v5.3: Use javascript "library" / Use typescript "library"
        elif self._match(TokenType.JAVASCRIPT) or (
            self._match_identifier() and self._current().value.lower() == 'typescript'
        ):
            is_ts = self._current().value.lower() == 'typescript'
            self._advance()  # consume javascript/typescript keyword
            lib_tok = self._current()
            if lib_tok.type != TokenType.STRING:
                kw = 'typescript' if is_ts else 'javascript'
                raise ParserError(f'Expected library name string after "Use {kw}".', line)
            self._advance()
            library = lib_tok.value

            # Optional alias: Use javascript "axios" as http
            alias = None
            if self._match(TokenType.AS):
                self._advance()
                alias_tok = self._expect_identifier('Expected alias name after "as".')
                alias = alias_tok.value
            else:
                # Auto-alias: sanitize package name (e.g. "@scope/my-lib" -> "my_lib")
                alias = library.split('/')[-1].replace('-', '_').replace('.', '_')

            self._end_statement()
            return ast.UseJSStatement(library, alias, is_ts, line)

        else:
            # New syntax: Use "package" is equivalent to Import "package"
            filepath_tok = self._current()
            if filepath_tok.type != TokenType.STRING:
                raise ParserError('Expected package name string after "Use".', line)
            self._advance()

            # Optional alias: Use "module" as Alias
            alias = None
            if self._current().type == TokenType.AS:
                self._advance()  # consume AS
                alias_tok = self._expect_identifier('Expected alias name after "as".')
                alias = alias_tok.value

            self._end_statement()
            return ast.ImportStatement(filepath_tok.value, line, alias=alias)

    # ─── v0.3: Wait ──────────────────────────────────────

    def _parse_wait(self):
        """Wait 2 seconds"""
        line = self._current().line
        self._advance()  # consume WAIT

        duration = self._parse_expression()

        # Optional "seconds"
        self._optional(TokenType.SECONDS)
        self._end_statement()

        return ast.WaitStatement(duration, line)

    # ─── v0.3: Constant ──────────────────────────────────

    def _parse_constant(self):
        """Constant PI = 3.14"""
        line = self._current().line
        self._advance()  # consume CONSTANT

        name_tok = self._expect_identifier('Expected constant name.')
        self._expect(TokenType.OP_ASSIGN, 'Expected "=" after constant name.')
        value = self._parse_expression()
        self._end_statement()

        return ast.ConstDeclaration(name_tok.value, value, line)

    # ─── v0.3: Assert ────────────────────────────────────

    def _parse_assert(self):
        """Assert expression"""
        line = self._current().line
        self._advance()  # consume ASSERT

        expression = self._parse_expression()
        self._end_statement()

        return ast.AssertStatement(expression, line)

    # ─── v0.3: NoteBlock (multi-line comment) ────────────

    def _parse_noteblock(self):
        """NoteBlock ... End — skip all content until End."""
        self._advance()  # consume NOTEBLOCK
        self._skip_newlines()

        # Skip everything until End
        while not self._match(TokenType.END, TokenType.EOF):
            self._advance()

        if self._match(TokenType.END):
            self._advance()
        self._end_statement()

        return None  # comments produce no AST node

    # ─── v0.5: Web Framework Parsing ─────────────────────

    def _parse_webapp(self):
        """Create WebApp called myApp"""
        line = self._current().line
        self._advance()  # consume CREATE
        self._expect(TokenType.WEBAPP)  # consume WEBAPP
        self._optional(TokenType.CALLED)  # optional "called"
        name_tok = self._expect_identifier('Expected app name')
        self._end_statement()
        return ast.WebApp(name_tok.value, line)

    def _parse_route(self):
        """Route "/path" shows ... End  or  Route "/path" responds with ... End"""
        line = self._current().line
        self._advance()  # consume ROUTE

        # Path
        path_tok = self._expect(TokenType.STRING, 'Expected route path string')
        path = path_tok.value

        # Response type: "shows" (page) or "responds with" (json/api)
        response_type = 'page'
        if self._match(TokenType.RESPONDS):
            self._advance()
            self._optional(TokenType.WITH)
            response_type = 'json'
        elif self._match(TokenType.SHOWS):
            self._advance()
            response_type = 'page'

        self._end_statement()
        self._skip_newlines()

        # Parse body until End
        body = []
        while not self._is_block_end():
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
            self._skip_newlines()

        self._consume_block_end()
        return ast.Route(path, response_type, body, line)

    def _parse_start_server(self):
        """Start myApp on port 3000"""
        line = self._current().line
        self._advance()  # consume START

        name_tok = self._expect_identifier('Expected app name')

        self._optional(TokenType.ON)
        self._optional(TokenType.PORT)

        port_expr = self._parse_expression()
        self._end_statement()
        return ast.StartServer(name_tok.value, port_expr, line)

    def _parse_page(self):
        """Page "Title" ... End — generates HTML page with elements"""
        line = self._current().line
        self._advance()  # consume PAGE

        title_tok = self._expect(TokenType.STRING, 'Expected page title string')
        self._end_statement()
        self._skip_newlines()

        elements = []
        head_directives = []
        stylesheets = []
        styles = []
        while not self._is_block_end():
            if self._token_starts_head_directive():
                directive = self._parse_head_directive()
                if directive:
                    head_directives.append(directive)
                self._skip_newlines()
                continue
            # Page-scoped CSS: a `Stylesheet`/`Style` block nested in a Page
            # renders only on this route (after any site-wide CSS).
            if self._match(TokenType.STYLESHEET):
                stylesheets.append(self._parse_stylesheet_def())
                self._skip_newlines()
                continue
            if self._match(TokenType.STYLE):
                styles.append(self._parse_style_def())
                self._skip_newlines()
                continue
            elem = self._parse_html_element()
            if elem:
                elements.append(elem)
            self._skip_newlines()

        self._consume_block_end()
        return ast.PageDef(title_tok.value, elements, line, head_directives, stylesheets, styles)

    def _parse_html_element(self):
        """Parse a single HTML element inside a Page block."""
        self._skip_newlines()
        tok = self._current()

        # v9.3.0 — Raw HTML escape hatch: `Raw HTML "<table>..."`.
        # Emits the string literally without escaping. The author takes
        # responsibility for safety; never wire user-controlled input here.
        if tok.type == TokenType.RAW and self._peek().type == TokenType.HTML_KW:
            self._advance()  # consume RAW
            self._advance()  # consume HTML
            content = self._expect(TokenType.STRING, 'Expected HTML string after `Raw HTML`').value
            self._end_statement()
            return ast.HtmlElement('raw_html', content, line=tok.line)

        if tok.type == TokenType.HEADING:
            self._advance()
            content = self._expect(TokenType.STRING, 'Expected heading text').value
            self._end_statement()
            return ast.HtmlElement('heading', content, line=tok.line)

        if tok.type == TokenType.SUBHEADING:
            self._advance()
            content = self._expect(TokenType.STRING, 'Expected subheading text').value
            self._end_statement()
            return ast.HtmlElement('subheading', content, line=tok.line)

        if tok.type in (TokenType.TYPE_TEXT, TokenType.SAY, TokenType.DISPLAY, TokenType.SHOW):
            is_store_list = tok.type in (TokenType.SAY, TokenType.DISPLAY, TokenType.SHOW) and (
                (hasattr(TokenType, 'ITEMS') and self._peek().type == TokenType.ITEMS)
                or (
                    self._peek().type in (TokenType.IDENTIFIER,) + self._SOFT_KEYWORDS
                    and str(self._peek().value).lower() == 'items'
                )
            )
            if is_store_list:
                self._advance()
                if hasattr(TokenType, 'ITEMS'):
                    self._optional(TokenType.ITEMS)
                if self._match_identifier() and str(self._current().value).lower() == 'items':
                    self._advance()
                self._optional(TokenType.FROM)
                collection_tok = self._expect(
                    TokenType.STRING, 'Expected collection name after list output keyword.'
                )
                attrs = {'collection': collection_tok.value}
                if self._match(TokenType.DELETE_KW):
                    self._advance()
                    del_tok = self._expect(TokenType.STRING, 'Expected delete action URL.')
                    attrs['delete_action'] = del_tok.value
                self._end_statement()
                return ast.HtmlElement('store_list', None, attrs, line=tok.line)

            if tok.type == TokenType.TYPE_TEXT or self._peek().type == TokenType.STRING:
                self._advance()
                content = self._expect(TokenType.STRING, 'Expected text content').value
                self._end_statement()
                return ast.HtmlElement('text', content, line=tok.line)

        if tok.type == TokenType.LINK:
            self._advance()
            content = self._expect(TokenType.STRING, 'Expected link text').value
            attrs = {}
            if self._match(TokenType.TO):
                self._advance()
                attrs['href'] = self._expect(TokenType.STRING, 'Expected link URL').value
            events = []
            self._collect_inline_attrs(attrs, events)
            self._end_statement()
            return ast.HtmlElement('link', content, attrs, line=tok.line, events=events)

        if tok.type == TokenType.IMAGE:
            self._advance()
            src = self._expect(TokenType.STRING, 'Expected image source').value
            self._end_statement()
            return ast.HtmlElement('image', None, {'src': src}, line=tok.line)

        if tok.type == TokenType.BUTTON:
            self._advance()
            content = self._expect(TokenType.STRING, 'Expected button text').value
            attrs = {}
            events = []
            self._collect_inline_attrs(attrs, events)
            if self._match(TokenType.DOES):
                self._advance()
                # Read the rest of the line as JS action
                action_parts = []
                while not self._match(TokenType.NEWLINE, TokenType.EOF):
                    action_parts.append(str(self._current().value))
                    self._advance()
                attrs['onclick'] = ' '.join(action_parts)
            self._end_statement()
            return ast.HtmlElement('button', content, attrs, line=tok.line, events=events)

        if tok.type == TokenType.INPUT:
            self._advance()
            name = self._expect(TokenType.STRING, 'Expected input name').value
            attrs = {'name': name}
            if self._match(TokenType.PLACEHOLDER):
                self._advance()
                attrs['placeholder'] = self._expect(TokenType.STRING).value
            self._end_statement()
            return ast.HtmlElement('input', None, attrs, line=tok.line)

        if tok.type == TokenType.FORM:
            self._advance()
            attrs = {}
            if self._match(TokenType.ACTION):
                self._advance()
                attrs['action'] = self._expect(TokenType.STRING).value
            self._end_statement()
            self._skip_newlines()

            children = []
            while not self._is_block_end():
                child = self._parse_html_element()
                if child:
                    children.append(child)
                self._skip_newlines()
            self._consume_block_end()
            return ast.HtmlElement('form', None, attrs, children, tok.line)

        if tok.type == TokenType.TYPE_LIST:
            self._advance()
            items = self._parse_expression()
            self._end_statement()
            return ast.HtmlElement('list', items, line=tok.line)

        if tok.type == TokenType.SCRIPT:
            return self._parse_script_element()

        # Nested Page
        if tok.type == TokenType.PAGE:
            return self._parse_page()

        # v7.0: Native Animation Components
        if tok.type == TokenType.WORDS_PULL_UP:
            self._advance()
            content = self._expect(TokenType.STRING, 'Expected WordsPullUp text').value
            attrs = {}
            if (
                self._match(TokenType.IDENTIFIER)
                and str(self._current().value).lower() == 'asterisk'
            ):
                self._advance()
                attrs['asterisk'] = self._expect(
                    TokenType.STRING, 'Expected asterisk value (e.g. "true")'
                ).value
            self._end_statement()
            return ast.HtmlElement('words_pull_up', content, attrs, line=tok.line)

        if tok.type == TokenType.NOISE_OVERLAY:
            self._advance()
            self._end_statement()
            return ast.HtmlElement('noise_overlay', None, {}, line=tok.line)

        if tok.type == TokenType.BG_NOISE:
            self._advance()
            self._end_statement()
            return ast.HtmlElement('bg_noise', None, {}, line=tok.line)

        if tok.type == TokenType.WORDS_PULL_UP_MULTI_STYLE:
            self._advance()
            self._end_statement()
            self._skip_newlines()
            children = []
            while not self._is_block_end():
                if self._match(TokenType.SEGMENT):
                    seg_tok = self._current()
                    self._advance()
                    seg_content = self._expect(TokenType.STRING, 'Expected Segment text').value
                    seg_attrs = {}
                    if self._match(TokenType.STYLE):
                        self._advance()
                        seg_attrs['style'] = self._expect(
                            TokenType.STRING, 'Expected style classes'
                        ).value
                    self._end_statement()
                    children.append(
                        ast.HtmlElement('segment', seg_content, seg_attrs, line=seg_tok.line)
                    )
                else:
                    self._advance()
                self._skip_newlines()
            self._consume_block_end()
            return ast.HtmlElement('words_pull_up_multi_style', None, {}, children, line=tok.line)

        # v6.0: Structural elements inside Page
        _structural_map = {
            TokenType.DIV: 'div',
            TokenType.SECTION: 'section',
            TokenType.NAV: 'nav',
            TokenType.HEADER_EL: 'header',
            TokenType.FOOTER_EL: 'footer',
            TokenType.SPAN: 'span',
            TokenType.ARTICLE: 'article',
            TokenType.ASIDE: 'aside',
            TokenType.MAIN_EL: 'main',
            TokenType.CONTAINER: 'container',
        }
        if tok.type in _structural_map:
            return self._parse_styled_element(_structural_map[tok.type])

        if tok.type == TokenType.FLEX:
            return self._parse_layout_container('flex')
        if tok.type == TokenType.GRID:
            return self._parse_layout_container('grid')

        # v6.1: 3D & Canvas inside Page
        if tok.type == TokenType.SCENE:
            return self._parse_scene_3d()
        if tok.type == TokenType.DRAW:
            return self._parse_draw_command()

        # Unknown element: skip line
        self._advance()
        self._end_statement()
        return None

    def _parse_send(self):
        """Send json <expr>  or  Send text <expr>"""
        line = self._current().line
        self._advance()  # consume SEND

        response_type = 'json'
        if self._match(TokenType.JSON):
            self._advance()
        elif self._match(TokenType.TYPE_TEXT):
            self._advance()
            response_type = 'text'

        data = self._parse_expression()
        self._end_statement()
        return ast.SendResponse(response_type, data, line)

    def _parse_script(self):
        """Script ... End — raw JavaScript block"""
        line = self._current().line
        self._advance()  # consume SCRIPT
        self._skip_newlines()

        # Collect all text until End
        code_parts = []
        while not self._is_block_end():
            tok = self._current()
            if tok.type == TokenType.EOF:
                break
            code_parts.append(str(tok.value))
            self._advance()
            if self._match(TokenType.NEWLINE):
                code_parts.append('\n')
                self._advance()

        self._consume_block_end()
        return ast.ScriptBlock(' '.join(code_parts), line)

    def _parse_script_element(self):
        """Same as _parse_script but returns HtmlElement for inside Page."""
        node = self._parse_script()
        return ast.HtmlElement('script', node.code, line=node.line)

    # ─── v0.5: Store / Fetch / Delete / Redirect ─────────

    def _parse_store(self):
        """
        Store form "field_name" in "collection"
        Store <expression> in "collection"
        """
        line = self._current().line
        self._advance()  # consume STORE

        # Check for "form" keyword → store a form field
        field_name = None
        value = None
        if self._match(TokenType.FORM):
            self._advance()  # consume FORM
            field_tok = self._expect(
                TokenType.STRING, 'Expected field name string after "Store form".'
            )
            field_name = field_tok.value
        else:
            value = self._parse_expression()

        self._expect(TokenType.IN, 'Expected "in" after Store value.')

        collection_tok = self._expect(
            TokenType.STRING, 'Expected collection name string after "in".'
        )
        collection = collection_tok.value

        self._end_statement()
        return ast.StoreStatement(collection, field_name=field_name, value=value, line=line)

    def _parse_fetch(self):
        """Fetch "collection" — expression that returns stored items."""
        line = self._current().line
        self._advance()  # consume FETCH

        collection_tok = self._expect(
            TokenType.STRING, 'Expected collection name string after "Fetch".'
        )
        collection = collection_tok.value

        self._end_statement()
        return ast.FetchStatement(collection, line)

    def _parse_delete(self):
        """Delete from "collection" at <index>"""
        line = self._current().line
        self._advance()  # consume DELETE_KW

        self._expect(TokenType.FROM, 'Expected "from" after "Delete".')

        collection_tok = self._expect(
            TokenType.STRING, 'Expected collection name string after "Delete from".'
        )
        collection = collection_tok.value

        index = None
        if self._match(TokenType.AT):
            self._advance()  # consume AT
            index = self._parse_expression()

        self._end_statement()
        return ast.DeleteStatement(collection, index=index, line=line)

    def _parse_redirect(self):
        """Redirect to "/path" """
        line = self._current().line
        self._advance()  # consume REDIRECT

        self._optional(TokenType.TO)

        url_tok = self._expect(TokenType.STRING, 'Expected URL string after "Redirect".')
        self._end_statement()

        return ast.SendResponse('redirect', ast.Literal(url_tok.value, line), line)

    # ─── v0.6: Lambda / Enum / Throw ─────────────────────

    def _parse_lambda(self):
        """lambda x, y -> x + y"""
        line = self._current().line
        self._advance()  # consume LAMBDA

        params = []
        # Parse parameter names until ->
        if not self._match(TokenType.ARROW):
            tok = self._expect_identifier('Expected parameter name in lambda.')
            params.append(tok.value)
            while self._match(TokenType.COMMA):
                self._advance()
                tok = self._expect_identifier('Expected parameter name in lambda.')
                params.append(tok.value)

        self._expect(TokenType.ARROW, 'Expected "->" in lambda expression.')
        body = self._parse_expression()
        return ast.LambdaExpression(params, body, line)

    def _parse_given(self):
        """given x, y return x + y  (English-style lambda)"""
        line = self._current().line
        self._advance()  # consume GIVEN

        params = []
        # Parse parameter names until "return" or "->"
        if not self._match(TokenType.RETURN) and not self._match(TokenType.ARROW):
            tok = self._expect_identifier('Expected parameter name after "given".')
            params.append(tok.value)
            while self._match(TokenType.COMMA):
                self._advance()
                tok = self._expect_identifier('Expected parameter name after "given".')
                params.append(tok.value)

        # Accept either "return" or "->"
        if self._match(TokenType.RETURN):
            self._advance()
        elif self._match(TokenType.ARROW):
            self._advance()
        else:
            raise ParserError(
                'Expected "return" or "->" after parameter names in given expression.',
                self._current().line,
            )

        body = self._parse_expression()
        return ast.LambdaExpression(params, body, line)

    def _parse_enum(self):
        """Define enum Color as Red, Green, Blue End"""
        line = self._current().line
        self._advance()  # consume ENUM

        name_tok = self._expect_identifier('Expected enum name after "Enum".')
        enum_name = name_tok.value

        # Optional "as"
        if self._match(TokenType.AS):
            self._advance()

        members = []
        tok = self._expect_identifier('Expected enum member name.')
        members.append(tok.value)
        while self._match(TokenType.COMMA):
            self._advance()
            tok = self._expect_identifier('Expected enum member name.')
            members.append(tok.value)

        self._end_statement()
        return ast.EnumDef(enum_name, members, line)

    def _parse_throw(self):
        """Throw "error message" or Throw expression"""
        line = self._current().line
        self._advance()  # consume THROW
        expr = self._parse_expression()
        self._end_statement()
        return ast.ThrowStatement(expr, line)

    # ─── v0.7: English List Operations ───────────────────

    def _parse_add_to(self):
        """Add 5 to myList  /  Add "hello" to items"""
        line = self._current().line
        self._advance()  # consume ADD

        value = self._parse_expression()

        self._expect(TokenType.TO, 'Expected "to" after value in "Add X to list".')

        list_name_tok = self._expect_identifier('Expected list name after "to".')
        list_name = list_name_tok.value

        self._end_statement()
        return ast.MethodCall(ast.Identifier(list_name, line), 'add', [value], line)

    def _parse_sort_statement(self):
        """Sort myList"""
        line = self._current().line
        self._advance()  # consume SORT

        list_name_tok = self._expect_identifier('Expected list name after "Sort".')
        list_name = list_name_tok.value

        self._end_statement()
        return ast.MethodCall(ast.Identifier(list_name, line), 'sort', [], line)

    def _parse_reverse_statement(self):
        """Reverse myList"""
        line = self._current().line
        self._advance()  # consume REVERSE

        list_name_tok = self._expect_identifier('Expected list name after "Reverse".')
        list_name = list_name_tok.value

        self._end_statement()
        return ast.MethodCall(ast.Identifier(list_name, line), 'reverse', [], line)

    # ─── v1.4: GUI Framework Parsing ─────────────────────

    def _parse_window(self):
        """Window "title" [width x height] ... End"""
        line = self._current().line
        self._advance()  # consume WINDOW
        title = self._parse_expression()
        width = None
        height = None
        # Optional size: number "by" number or number "x" number
        if self._match(TokenType.NUMBER):
            width = self._parse_expression()
            if self._match(TokenType.BY) or (
                self._match_identifier() and self._current().value.lower() == 'x'
            ):
                self._advance()
                height = self._parse_expression()
        self._skip_newlines()
        body = []
        while not self._match(TokenType.END) and not self._match(TokenType.EOF):
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
            self._skip_newlines()
        if self._match(TokenType.END):
            self._advance()
        self._end_statement()
        return ast.WindowCreate(title, width, height, body, line)

    def _parse_widget_add(self, widget_type):
        """Button "Click Me" called btn1 does handleClick.
        Label "Hello" called lbl1.
        TextBox called input1 placeholder "Enter text".
        Dropdown ["a", "b"] called dd1.
        Slider 0 to 100 called sl1.
        Progress 50 called pb1."""
        line = self._current().line
        self._advance()  # consume widget keyword
        text = None
        name = None
        action = None
        props = {}

        # Parse text/value (optional for some widgets)
        if (
            self._match(TokenType.STRING)
            or self._match(TokenType.NUMBER)
            or self._match(TokenType.LBRACKET)
        ):
            text = self._parse_expression()

        # "called name" or "as name"
        if self._match(TokenType.CALLED) or self._match(TokenType.AS):
            self._advance()
            name_tok = self._expect_identifier('Expected widget name.')
            name = name_tok.value

        # "does action" (for buttons)
        if self._match(TokenType.DOES):
            self._advance()
            action = self._parse_expression()

        # Optional properties: "placeholder ..." "action ..."
        if self._match(TokenType.PLACEHOLDER):
            self._advance()
            props['placeholder'] = self._parse_expression()
        if self._match(TokenType.ACTION):
            self._advance()
            action = self._parse_expression()

        # "to" for range (slider)
        if self._match(TokenType.TO):
            self._advance()
            props['max'] = self._parse_expression()

        self._end_statement()
        return ast.WidgetAdd(widget_type, text, name, action, props, line)

    def _parse_layout_block(self, direction):
        """Row ... End / Column ... End"""
        line = self._current().line
        self._advance()  # consume ROW/COLUMN
        self._skip_newlines()
        children = []
        while not self._match(TokenType.END) and not self._match(TokenType.EOF):
            stmt = self._parse_statement()
            if stmt:
                children.append(stmt)
            self._skip_newlines()
        if self._match(TokenType.END):
            self._advance()
        self._end_statement()
        return ast.LayoutBlock(direction, children, line)

    def _parse_bind_event(self):
        """Bind widgetName "click" to handlerFunc"""
        line = self._current().line
        self._advance()  # consume BIND
        name_tok = self._expect_identifier('Expected widget name after "Bind".')
        widget_name = name_tok.value
        event_type_expr = self._parse_expression()
        self._expect(TokenType.TO, 'Expected "to" in Bind statement.')
        handler = self._parse_expression()
        self._end_statement()
        return ast.BindEvent(widget_name, event_type_expr, handler, line)

    def _parse_dialog(self):
        """Dialog "message" [type "info"|"error"|"yesno"|"input"]"""
        line = self._current().line
        self._advance()  # consume DIALOG
        message = self._parse_expression()
        dialog_type = 'info'
        title = None
        if self._match(TokenType.TYPE):
            self._advance()
            dt_expr = self._parse_expression()
            if isinstance(dt_expr, ast.Literal):
                dialog_type = str(dt_expr.value)
        self._end_statement()
        return ast.DialogShow(message, dialog_type, title, line)

    def _parse_menu_def(self):
        """Menu "File" ... End"""
        line = self._current().line
        self._advance()  # consume MENU
        label_expr = self._parse_expression()
        label = label_expr.value if isinstance(label_expr, ast.Literal) else str(label_expr)
        self._skip_newlines()
        items = []
        while not self._match(TokenType.END) and not self._match(TokenType.EOF):
            stmt = self._parse_statement()
            if stmt:
                items.append(stmt)
            self._skip_newlines()
        if self._match(TokenType.END):
            self._advance()
        self._end_statement()
        return ast.MenuDef(label, items, line)

    def _parse_canvas_draw(self):
        """Canvas canvasName draw rect/circle/line x y w h color "red" """
        line = self._current().line
        self._advance()  # consume CANVAS
        canvas_tok = self._expect_identifier('Expected canvas name.')
        canvas_name = canvas_tok.value
        # expect "draw"
        if self._match_identifier() and self._current().value.lower() == 'draw':
            self._advance()
        shape_tok = self._expect_identifier('Expected shape name (rect, circle, line, text).')
        shape = shape_tok.value.lower()
        props = {}
        # Parse property pairs: x 10 y 20 width 100 height 50 color "red"
        while (
            not self._match(TokenType.DOT)
            and not self._match(TokenType.NEWLINE)
            and not self._match(TokenType.EOF)
        ):
            if self._match_identifier():
                key = self._current().value
                self._advance()
                val = self._parse_expression()
                props[key] = val
            else:
                break
        self._end_statement()
        return ast.CanvasDraw(canvas_name, shape, props, line)

    # ─── v1.4: Async/Await/Super ─────────────────────────

    def _parse_async_function(self):
        """Async Function name takes params ... End"""
        line = self._current().line
        self._advance()  # consume ASYNC
        # Expect Function keyword
        if self._match(TokenType.FUNCTION):
            self._advance()
        elif self._match(TokenType.DEFINE):
            self._advance()
            self._expect(TokenType.FUNCTION, 'Expected "Function" after "Async".')
        else:
            raise ParserError('Expected "Function" after "Async".', line)
        name_tok = self._expect_identifier('Expected function name.')
        func_name = name_tok.value
        params = []
        if self._match(TokenType.THAT):
            self._advance()
            self._expect(TokenType.TAKES, 'Expected "takes" after "that".')
            params = self._parse_param_list()
        elif self._match(TokenType.TAKES):
            self._advance()
            params = self._parse_param_list()
        return_type = None
        if self._match(TokenType.AND):
            self._advance()
            self._expect(TokenType.RETURNS, 'Expected "returns" after "and".')
            if self._match(
                TokenType.TYPE_INTEGER,
                TokenType.TYPE_DECIMAL,
                TokenType.TYPE_TEXT,
                TokenType.TYPE_BOOLEAN,
                TokenType.TYPE_LIST,
                TokenType.NOTHING,
            ):
                return_type = self._advance().value.lower()
        elif self._match(TokenType.RETURNS):
            self._advance()
            rt_tok = self._advance()
            return_type = rt_tok.value
        self._end_statement()
        self._skip_newlines()
        body = []
        while not self._match(TokenType.END, TokenType.END_FUNCTION, TokenType.EOF):
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
            self._skip_newlines()
        self._consume_block_end()
        return ast.AsyncFunctionDef(func_name, params, return_type, body, line)

    def _parse_spawn(self):
        """Spawn task_name calling func(args)  OR  Spawn call func(args)"""
        line = self._current().line
        self._advance()  # consume SPAWN
        # Check for named spawn: Spawn task_name calling func with args
        var_name = None
        if self._match_identifier():
            saved = self.pos
            name_tok = self._advance()
            if self._match(TokenType.CALLED) or (
                self._match_identifier() and self._current().value.lower() == 'calling'
            ):
                var_name = name_tok.value
                self._advance()  # consume 'calling'/'called'
            else:
                self.pos = saved  # rewind — it's the function name or 'call'
        # Now parse the function call expression
        # Accept: call func with args  OR  func with args  OR  func(args)
        if self._match(TokenType.CALL):
            expr = self._parse_call_expression()
        elif self._match_identifier():
            # Direct function name: Spawn task calling myFunc with args
            name_tok = self._expect_identifier('Expected function name in Spawn.')
            func_name = name_tok.value
            arguments = []
            if self._match(TokenType.WITH):
                self._advance()
                arguments = self._parse_arg_list()
            expr = ast.FunctionCall(func_name, arguments, line)
        else:
            expr = self._parse_expression()
        self._end_statement()
        if var_name is None:
            var_name = f'_spawn_{line}'
        return ast.SpawnStatement(var_name, expr, line)

    def _parse_parallel_for_each(self):
        """Parallel For Each item in collection ... End"""
        line = self._current().line
        self._advance()  # consume PARALLEL
        if not self._match(TokenType.FOR):
            raise ParserError('Expected "For" after "Parallel".', line)
        self._advance()  # consume FOR
        if self._match(TokenType.EACH):
            self._advance()  # consume EACH
        var_tok = self._expect_identifier('Expected variable name in Parallel For Each.')
        var_name = var_tok.value
        if self._match(TokenType.IN):
            self._advance()
        else:
            raise ParserError('Expected "in" after variable in Parallel For Each.', line)
        iterable = self._parse_expression()
        max_workers = None
        if self._match(TokenType.WITH):
            self._advance()
            max_workers_expr = self._parse_expression()
            if isinstance(max_workers_expr, ast.Literal) and isinstance(
                max_workers_expr.value, (int, float)
            ):
                max_workers = int(max_workers_expr.value)
            if self._match_identifier() and self._current().value.lower() == 'workers':
                self._advance()
        self._end_statement()
        self._skip_newlines()
        body = []
        while not self._match(TokenType.END, TokenType.EOF):
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
            self._skip_newlines()
        self._consume_block_end()
        return ast.ParallelForEach(var_name, iterable, body, max_workers, line)

    def _parse_breakpoint_stmt(self):
        """Breakpoint [if condition]"""
        line = self._current().line
        self._advance()  # consume BREAKPOINT_KW
        condition = None
        if self._match(TokenType.IF):
            self._advance()
            condition = self._parse_expression()
        self._end_statement()
        return ast.BreakpointStatement(condition, line)

    # ─── v5.2: Triple Ecosystem Parsers ───────────────────────────────────

    def _parse_external_function(self):
        """External function <name> from "<library>" takes (<types>) returns <type>
        External function <name> from "<library>" takes nothing returns <type>"""
        line = self._current().line
        self._advance()  # consume EXTERNAL

        # Expect 'function' keyword
        if not (self._match(TokenType.FUNCTION) or self._match(TokenType.DEFINE)):
            raise ParserError('Expected "function" after "External".', line)
        self._advance()

        # Function name
        name_tok = self._expect_identifier('Expected function name in External declaration.')
        func_name = name_tok.value

        # Expect 'from' keyword
        if not (self._match_identifier() and self._current().value.lower() == 'from'):
            raise ParserError('Expected "from" after function name in External declaration.', line)
        self._advance()  # consume 'from'

        # Library name (string)
        if self._current().type != TokenType.STRING:
            raise ParserError('Expected library path string after "from".', line)
        library = self._current().value
        self._advance()

        # Expect 'takes' keyword
        if not self._match(TokenType.TAKES):
            raise ParserError('Expected "takes" in External function declaration.', line)
        self._advance()

        # Parameter types: "nothing" or "(type1, type2, ...)"
        param_types = []
        if self._match(TokenType.NOTHING):
            self._advance()
        elif self._match(TokenType.LPAREN):
            self._advance()  # consume (
            while not self._match(TokenType.RPAREN):
                if self._match(TokenType.COMMA):
                    self._advance()
                    continue
                type_tok = self._expect_identifier('Expected type name in parameter list.')
                param_types.append(type_tok.value)
            self._advance()  # consume )
        else:
            # Single type without parens
            type_tok = self._expect_identifier('Expected parameter type or "nothing".')
            param_types.append(type_tok.value)

        # Expect 'returns' keyword
        ret_type = 'void'
        if self._match(TokenType.RETURNS) or self._match(TokenType.RETURN):
            self._advance()
            ret_tok = self._expect_identifier('Expected return type.')
            ret_type = ret_tok.value

        # Optional alias: 'as <name>'
        alias = None
        if self._match(TokenType.AS):
            self._advance()
            alias_tok = self._expect_identifier('Expected alias name after "as".')
            alias = alias_tok.value

        self._end_statement()
        return ast.ExternalFunctionDef(func_name, library, param_types, ret_type, alias, line)

    def _parse_load_library(self):
        """Load library "path" as name"""
        line = self._current().line
        self._advance()  # consume 'Load' identifier
        self._advance()  # consume LIBRARY

        # Library path (string)
        if self._current().type != TokenType.STRING:
            raise ParserError('Expected library path string after "Load library".', line)
        path = self._current().value
        self._advance()

        # Expect 'as' keyword
        if not self._match(TokenType.AS):
            raise ParserError('Expected "as" after library path.', line)
        self._advance()

        # Alias name
        alias_tok = self._expect_identifier('Expected alias name after "as".')
        alias = alias_tok.value

        self._end_statement()
        return ast.LoadLibrary(path, alias, line)

    def _parse_await_statement(self):
        """Await expression."""
        line = self._current().line
        self._advance()  # consume AWAIT
        expr = self._parse_expression()
        self._end_statement()
        # Wrap as a var declaration with await, or expression statement
        return ast.VarDeclaration('_await_result', ast.AwaitExpression(expr, line), line=line)

    def _parse_super_call(self):
        """Super.method(args) or Super(args)"""
        line = self._current().line
        self._advance()  # consume SUPER
        method_name = None
        arguments = []
        if self._match(TokenType.DOT):
            self._advance()
            method_tok = self._expect_identifier('Expected method name after "Super.".')
            method_name = method_tok.value
        if self._match(TokenType.LPAREN):
            self._advance()
            if not self._match(TokenType.RPAREN):
                arguments.append(self._parse_expression())
                while self._match(TokenType.COMMA):
                    self._advance()
                    arguments.append(self._parse_expression())
            self._expect(TokenType.RPAREN, 'Expected ")" after super arguments.')
        self._end_statement()
        return ast.SuperCall(method_name, arguments, line)

    # ─── v4.0: Interface Definition ──────────────────────

    def _parse_interface_def(self):
        """Interface Printable ... End"""
        line = self._current().line
        self._advance()  # consume INTERFACE

        name_tok = self._expect_identifier('Expected interface name.')
        iface_name = name_tok.value

        # Optional extends
        extends = []
        if self._match(TokenType.EXTENDS):
            self._advance()
            ext_tok = self._expect_identifier('Expected parent interface name.')
            extends.append(ext_tok.value)
            while self._match(TokenType.COMMA):
                self._advance()
                ext_tok = self._expect_identifier('Expected interface name.')
                extends.append(ext_tok.value)

        self._end_statement()
        self._skip_newlines()

        methods = []
        while not self._match(TokenType.END, TokenType.EOF):
            # Parse method signatures: Function name takes params and returns type
            if self._match(TokenType.DEFINE, TokenType.FUNCTION):
                sig = self._parse_interface_method_sig()
                if sig:
                    methods.append(sig)
            else:
                self._advance()  # skip unknown tokens inside interface
            self._skip_newlines()

        self._consume_block_end()
        return ast.InterfaceDefNode(iface_name, methods, extends, line)

    def _parse_interface_method_sig(self):
        """Parse a method signature inside an interface (no body)."""
        line = self._current().line

        if self._match(TokenType.DEFINE):
            self._advance()
            self._optional(TokenType.A, TokenType.AN, TokenType.THE)
            self._expect(TokenType.FUNCTION, 'Expected "function" in interface method signature.')
            self._optional(TokenType.NAMED)
        else:
            self._advance()  # consume FUNCTION

        name_tok = self._expect_identifier('Expected method name.')
        method_name = name_tok.value

        params = []
        if self._match(TokenType.THAT):
            self._advance()
            self._expect(TokenType.TAKES, 'Expected "takes".')
            params = self._parse_param_list()
        elif self._match(TokenType.TAKES):
            self._advance()
            params = self._parse_param_list()

        return_type = None
        if self._match(TokenType.AND):
            self._advance()
            self._expect(TokenType.RETURNS, 'Expected "returns".')
            if self._match(
                TokenType.TYPE_INTEGER,
                TokenType.TYPE_DECIMAL,
                TokenType.TYPE_TEXT,
                TokenType.TYPE_BOOLEAN,
                TokenType.TYPE_LIST,
                TokenType.NOTHING,
            ):
                return_type = self._advance().value.lower()

        self._end_statement()
        return (method_name, params, return_type)

    # ─── v4.0: Module Definition ─────────────────────────

    def _parse_module_def(self):
        """Module MathUtils ... End"""
        line = self._current().line
        self._advance()  # consume MODULE

        name_tok = self._expect_identifier('Expected module name.')
        mod_name = name_tok.value

        self._end_statement()
        self._skip_newlines()

        body = []
        exports = []
        while not self._match(TokenType.END, TokenType.EOF):
            if self._match(TokenType.EXPORT):
                exp_line = self._current().line
                self._advance()  # consume EXPORT
                exp_tok = self._expect_identifier('Expected name to export.')
                exports.append(exp_tok.value)
                self._end_statement()
            else:
                stmt = self._parse_statement()
                if stmt:
                    body.append(stmt)
            self._skip_newlines()

        self._consume_block_end()
        return ast.ModuleDef(mod_name, body, exports, line)

    # ─── v4.0: Export Statement ──────────────────────────

    def _parse_export(self):
        """Export functionName"""
        line = self._current().line
        self._advance()  # consume EXPORT
        name_tok = self._expect_identifier('Expected name to export.')
        self._end_statement()
        return ast.ExportStatement(name_tok.value, line)

    # ─── v4.0: Visibility Modifiers ──────────────────────

    def _parse_visibility_modifier(self):
        """Public/Private/Protected <statement>"""
        line = self._current().line
        vis = self._advance().value.lower()  # consume visibility token
        stmt = self._parse_statement()
        return ast.VisibilityModifier(vis, stmt, line)

    # ─── v4.0: Static Method ─────────────────────────────

    def _parse_static_method(self):
        """Static Function name ... End"""
        line = self._current().line
        self._advance()  # consume STATIC

        # Delegate to function def parsing
        if self._match(TokenType.DEFINE):
            func = self._parse_function_def()
        elif self._match(TokenType.FUNCTION):
            func = self._parse_function_def_short()
        else:
            raise ParserError('Expected "Define" or "Function" after "Static".', line)

        return ast.StaticMethodDef(func.name, func.params, func.return_type, func.body, line)

    # ─── v4.0: Abstract Method ───────────────────────────

    def _parse_abstract_method(self):
        """Abstract Function name takes params and returns type"""
        line = self._current().line
        self._advance()  # consume ABSTRACT

        self._optional(TokenType.DEFINE)
        self._expect(TokenType.FUNCTION, 'Expected "Function" after "Abstract".')
        self._optional(TokenType.NAMED)

        name_tok = self._expect_identifier('Expected method name.')

        params = []
        if self._match(TokenType.THAT):
            self._advance()
            self._expect(TokenType.TAKES, 'Expected "takes".')
            params = self._parse_param_list()
        elif self._match(TokenType.TAKES):
            self._advance()
            params = self._parse_param_list()

        return_type = None
        if self._match(TokenType.AND):
            self._advance()
            self._expect(TokenType.RETURNS, 'Expected "returns".')
            if self._match(
                TokenType.TYPE_INTEGER,
                TokenType.TYPE_DECIMAL,
                TokenType.TYPE_TEXT,
                TokenType.TYPE_BOOLEAN,
                TokenType.TYPE_LIST,
                TokenType.NOTHING,
            ):
                return_type = self._advance().value.lower()

        self._end_statement()
        return ast.AbstractMethodDef(name_tok.value, params, return_type, line)

    # ─── v4.0: Yield Statement ───────────────────────────

    def _parse_yield(self):
        """Yields value"""
        line = self._current().line
        self._advance()  # consume YIELDS
        value = None
        if not self._match(TokenType.NEWLINE, TokenType.EOF):
            value = self._parse_expression()
        self._end_statement()
        return ast.YieldStatement(value, line)

    # ─── v4.0: Override Method ───────────────────────────

    def _parse_override_method(self):
        """Override Function name ... End"""
        line = self._current().line
        self._advance()  # consume OVERRIDE
        # Just parse the function normally — the Override is a marker for validation
        if self._match(TokenType.DEFINE):
            return self._parse_function_def()
        elif self._match(TokenType.FUNCTION):
            return self._parse_function_def_short()
        raise ParserError('Expected "Define" or "Function" after "Override".', line)

    # ─── v6.0: Style & Layout System ─────────────────────

    # Element-starting tokens that `_parse_html_element` fully handles and that
    # are unambiguous as web elements when nested inside a structural block
    # (Div/Section/Nav/…). Kept in sync with the dispatch in
    # `_parse_html_element`; `TYPE_TEXT`/`SAY`/`DISPLAY`/`SHOW` are handled
    # separately below because they double as statement keywords.
    _NESTED_ELEMENT_TOKENS = frozenset(
        {
            TokenType.HEADING,
            TokenType.SUBHEADING,
            TokenType.LINK,
            TokenType.IMAGE,
            TokenType.BUTTON,
            TokenType.INPUT,
            TokenType.FORM,
            TokenType.TYPE_LIST,
            TokenType.SCRIPT,
            TokenType.PAGE,
            TokenType.WORDS_PULL_UP,
            TokenType.NOISE_OVERLAY,
            TokenType.BG_NOISE,
            TokenType.WORDS_PULL_UP_MULTI_STYLE,
            TokenType.DIV,
            TokenType.SECTION,
            TokenType.NAV,
            TokenType.HEADER_EL,
            TokenType.FOOTER_EL,
            TokenType.SPAN,
            TokenType.ARTICLE,
            TokenType.ASIDE,
            TokenType.MAIN_EL,
            TokenType.CONTAINER,
            TokenType.FLEX,
            TokenType.GRID,
        }
    )

    def _parse_element_or_statement(self):
        """Try to parse as HTML element first, then fall back to statement."""
        tok = self._current()
        nxt = self._peek()
        # `Raw HTML "..."` — two-token element, must be checked before the set.
        if tok.type == TokenType.RAW and nxt and nxt.type == TokenType.HTML_KW:
            return self._parse_html_element()
        if tok.type in self._NESTED_ELEMENT_TOKENS:
            return self._parse_html_element()
        if tok.type == TokenType.TYPE_TEXT and nxt and nxt.type == TokenType.STRING:
            return self._parse_html_element()
        if tok.type in (TokenType.SAY, TokenType.DISPLAY, TokenType.SHOW):
            if nxt and nxt.type == TokenType.STRING:
                return self._parse_html_element()
        return self._parse_statement()

    # Pseudo-elements get `::`; everything else after `On` is a pseudo-class.
    _PSEUDO_ELEMENTS = frozenset(
        {
            'before',
            'after',
            'placeholder',
            'selection',
            'first-line',
            'first-letter',
            'marker',
            'backdrop',
        }
    )
    # Named responsive breakpoints → media-query conditions.
    _NAMED_BREAKPOINTS = {
        'mobile': '(max-width: 640px)',
        'tablet': '(max-width: 1024px)',
        'desktop': '(min-width: 1025px)',
    }

    @staticmethod
    def _css_pseudo_ok(name):
        """Validate a pseudo-state name: lowercase letters and hyphens only."""
        return (
            bool(name)
            and name[0].isalpha()
            and name == name.lower()
            and all(c.isalpha() or c == '-' for c in name)
        )

    @staticmethod
    def _css_width_ok(width):
        """Validate a media width like "640px", "40rem", "100%"."""
        w = width.strip()
        for unit in ('px', 'rem', 'em', '%', 'vw', 'vh'):
            if w.endswith(unit):
                num = w[: -len(unit)]
                return len(num) > 0 and num.isdigit()
        return w.isdigit()

    def _parse_style_property_block(self):
        """Parse CSS property lines until (not consuming) End/EOF."""
        props = []
        while not self._match(TokenType.END, TokenType.EOF):
            self._skip_newlines()
            if self._match(TokenType.END, TokenType.EOF):
                break
            prop = self._parse_style_property()
            if prop:
                props.append(prop)
        return props

    def _parse_style_on_block(self):
        """Parse an `On <pseudo|breakpoint>` block inside a Style, returning a
        StyleRule. Handles pseudo-classes/elements, named breakpoints, and
        `On screen below|above "Npx"` explicit media queries."""
        line = self._current().line
        self._advance()  # consume ON
        name = self._read_attr_name()  # reassembles hyphenated names (focus-visible)
        if not name:
            raise ParserError('Expected a pseudo-state or breakpoint after "On".', line)

        media = None
        suffix = ''
        if name in self._NAMED_BREAKPOINTS:
            media = self._NAMED_BREAKPOINTS[name]
        elif name == 'screen':
            direction = self._read_attr_name()
            if direction not in ('below', 'above'):
                raise ParserError('Expected "below" or "above" after "On screen".', line)
            width_tok = self._expect(
                TokenType.STRING, 'Expected a width string (e.g. "640px") after On screen.'
            )
            if not self._css_width_ok(width_tok.value):
                raise ParserError(
                    f'Invalid media width "{width_tok.value}". Use e.g. "640px" or "40rem".',
                    width_tok.line,
                )
            cond = 'max-width' if direction == 'below' else 'min-width'
            media = f'({cond}: {width_tok.value})'
        else:
            if not self._css_pseudo_ok(name):
                raise ParserError(f'Invalid pseudo-state "{name}" after "On".', line)
            suffix = ('::' if name in self._PSEUDO_ELEMENTS else ':') + name

        self._end_statement()
        props = self._parse_style_property_block()
        self._expect(TokenType.END, 'Expected "End" to close the "On" block.')
        self._end_statement()
        return ast.StyleRule(suffix, props, media, line)

    def _parse_style_select_block(self):
        """Parse a `Select "selector"` descendant block, returning a StyleRule."""
        line = self._current().line
        self._advance()  # consume `select` identifier
        sel_tok = self._expect(TokenType.STRING, 'Expected a selector string after "Select".')
        self._end_statement()
        props = self._parse_style_property_block()
        self._expect(TokenType.END, 'Expected "End" to close the "Select" block.')
        self._end_statement()
        return ast.StyleRule(f' {sel_tok.value}', props, None, line)

    def _parse_style_def(self):
        """Style "card"
            Background "#fff"
            On hover
                Background "#eee"
            End
            On mobile
                Padding "12px"
            End
            Select "a"
                Color "#007DF3"
            End
        End"""
        line = self._current().line
        self._advance()  # consume STYLE
        name_tok = self._expect(TokenType.STRING, 'Expected style name after "Style".')
        self._end_statement()

        properties = []
        rules = []
        while not self._match(TokenType.END, TokenType.EOF):
            self._skip_newlines()
            if self._match(TokenType.END, TokenType.EOF):
                break
            tok = self._current()
            if tok.type == TokenType.ON:
                rules.append(self._parse_style_on_block())
                continue
            if tok.type == TokenType.IDENTIFIER and str(tok.value).lower() == 'select':
                rules.append(self._parse_style_select_block())
                continue
            prop = self._parse_style_property()
            if prop:
                properties.append(prop)

        self._expect(TokenType.END, 'Expected "End" to close Style block.')
        self._end_statement()
        return ast.StyleDef(name_tok.value, properties, line, rules)

    def _parse_stylesheet_def(self):
        """Stylesheet ... End — first-class raw-CSS block (server-rendered).

        The lexer captures the body as a single STRING token (like Script).
        """
        line = self._current().line
        self._advance()  # consume STYLESHEET
        self._skip_newlines()
        css_parts = []
        while not self._is_block_end():
            tok = self._current()
            if tok.type == TokenType.EOF:
                break
            css_parts.append(str(tok.value))
            self._advance()
            if self._match(TokenType.NEWLINE):
                self._advance()
        self._consume_block_end()
        return ast.RawStylesheet('\n'.join(css_parts), line)

    # ─── Phase 3: Head / SEO directives ──────────────────────
    # Directive names recognised inside a Head block or as per-Page overrides.
    _HEAD_DIRECTIVE_NAMES = frozenset(
        {
            'description',
            'keywords',
            'author',
            'themecolor',
            'canonical',
            'favicon',
            'font',
            'opengraph',
            'twitter',
            'meta',
        }
    )

    def _token_starts_head_directive(self):
        """Whether the current token begins a head directive (used to collect
        per-Page overrides without consuming body elements)."""
        tok = self._current()
        if (
            tok.type == TokenType.IDENTIFIER
            and str(tok.value).lower() in self._HEAD_DIRECTIVE_NAMES
        ):
            return True
        # `Link rel ...`/`Link href ...` is a head link; `Link "text" to ...` is
        # a body anchor — disambiguate by the token right after LINK.
        if tok.type == TokenType.LINK:
            nxt = self._peek()
            return bool(nxt) and nxt.type != TokenType.STRING
        return False

    @staticmethod
    def _font_weights_ok(weights):
        """Validate a font-weights spec like "400;500;700"."""
        return bool(weights) and all(c.isdigit() or c == ';' for c in weights)

    @staticmethod
    def _meta_name_ok(name):
        """Validate a generic <meta name> — letters/digits and : _ - only."""
        return bool(name) and name[0].isalpha() and all(c.isalnum() or c in ':_-' for c in name)

    def _read_kv_pairs(self, allowed=None):
        """Read trailing `key "value"` pairs on a directive line into a dict.

        Keys are reassembled (hyphenated) identifiers; values are STRING.
        Stops at NEWLINE/EOF/DOT. If `allowed` is given, unknown keys raise.
        """
        pairs = {}
        while not self._match(TokenType.NEWLINE, TokenType.EOF, TokenType.DOT):
            saved = self.pos
            key = self._read_attr_name()
            if key is None or not self._match(TokenType.STRING):
                self.pos = saved
                break
            value = self._advance().value
            if allowed is not None and key not in allowed:
                raise ParserError(
                    f'Unknown option "{key}". Allowed: {", ".join(sorted(allowed))}.',
                    self._current().line,
                )
            pairs[key] = value
        return pairs

    def _parse_head_directive(self):
        """Parse one head/SEO directive line into a HeadDirective, or None."""
        tok = self._current()
        line = tok.line

        if tok.type == TokenType.LINK:
            self._advance()
            attrs = self._read_kv_pairs(
                allowed={'rel', 'href', 'as', 'type', 'crossorigin', 'media', 'sizes', 'hreflang'}
            )
            self._end_statement()
            return ast.HeadDirective('link', attrs, line)

        name = str(tok.value).lower()
        self._advance()

        # Simple single-string name=content meta directives.
        _SIMPLE = {
            'description': ('meta_name', 'description'),
            'keywords': ('meta_name', 'keywords'),
            'author': ('meta_name', 'author'),
            'themecolor': ('meta_name', 'theme-color'),
        }
        if name in _SIMPLE:
            value = self._expect(TokenType.STRING, f'Expected a string after "{tok.value}".').value
            self._end_statement()
            _, meta_name = _SIMPLE[name]
            return ast.HeadDirective('meta', {'name': meta_name, 'content': value}, line)

        if name == 'canonical':
            url = self._expect(TokenType.STRING, 'Expected a URL after "Canonical".').value
            self._end_statement()
            return ast.HeadDirective('canonical', {'href': url}, line)

        if name == 'favicon':
            url = self._expect(TokenType.STRING, 'Expected a URL after "Favicon".').value
            self._end_statement()
            return ast.HeadDirective('favicon', {'href': url}, line)

        if name == 'font':
            family = self._expect(TokenType.STRING, 'Expected a font family after "Font".').value
            attrs = self._read_kv_pairs(allowed={'weights'})
            weights = attrs.get('weights', '400')
            if not self._font_weights_ok(weights):
                raise ParserError(
                    f'Invalid font weights "{weights}". Use e.g. "400;500;700".', line
                )
            self._end_statement()
            return ast.HeadDirective('font', {'family': family, 'weights': weights}, line)

        if name == 'opengraph':
            attrs = self._read_kv_pairs(
                allowed={'title', 'description', 'type', 'image', 'url', 'site_name'}
            )
            self._end_statement()
            return ast.HeadDirective('opengraph', attrs, line)

        if name == 'twitter':
            attrs = self._read_kv_pairs(
                allowed={'card', 'title', 'description', 'image', 'site', 'creator'}
            )
            self._end_statement()
            return ast.HeadDirective('twitter', attrs, line)

        if name == 'meta':
            meta_name = self._expect(TokenType.STRING, 'Expected meta name after "Meta".').value
            content = self._expect(TokenType.STRING, 'Expected meta content after the name.').value
            if not self._meta_name_ok(meta_name):
                raise ParserError(f'Invalid meta name "{meta_name}".', line)
            self._end_statement()
            return ast.HeadDirective('meta', {'name': meta_name, 'content': content}, line)

        # Unknown directive — skip the line defensively.
        self._end_statement()
        return None

    def _parse_head_def(self):
        """Head ... End — a block of site-wide SEO/meta directives."""
        line = self._current().line
        self._advance()  # consume HEAD
        self._end_statement()
        self._skip_newlines()

        directives = []
        while not self._match(TokenType.END, TokenType.EOF):
            self._skip_newlines()
            if self._match(TokenType.END, TokenType.EOF):
                break
            directive = self._parse_head_directive()
            if directive:
                directives.append(directive)

        self._expect(TokenType.END, 'Expected "End" to close Head block.')
        self._end_statement()
        return ast.HeadDef(directives, line)

    def _parse_style_property(self):
        """Parse a CSS property line: Background "#fff" or Border radius "12px" """
        line = self._current().line
        parts = []

        while not self._match(
            TokenType.STRING, TokenType.NUMBER, TokenType.NEWLINE, TokenType.EOF, TokenType.END
        ):
            tok = self._current()
            parts.append(tok.value.lower() if tok.value else '')
            self._advance()

        if not parts:
            if self._match(TokenType.NEWLINE):
                self._advance()
            return None

        if self._match(TokenType.STRING):
            value = self._advance().value
        elif self._match(TokenType.NUMBER):
            value = str(self._advance().value)
        else:
            self._end_statement()
            return None

        property_name = '-'.join(parts)
        self._end_statement()
        return ast.StyleProperty(property_name, value, line)

    # Attribute names allowed on elements via the generic `name "value"` form.
    # Exact names plus the `aria-*`/`data-*` prefixes (checked separately).
    # Event handlers (`on*`) and `style`/`class`/`id` are deliberately excluded
    # — inline JS handlers route through the native event system (a later
    # phase), and style/class/id have dedicated parsing above.
    _SAFE_ATTR_NAMES = frozenset(
        {
            'role',
            'target',
            'rel',
            'title',
            'lang',
            'dir',
            'tabindex',
            'download',
            'hidden',
            'draggable',
            'spellcheck',
            'translate',
            'itemprop',
            'itemscope',
            'itemtype',
        }
    )

    def _read_attr_name(self):
        """Read a (possibly hyphenated) attribute name like `aria-label`.

        Hyphenated names lex as separate tokens (IDENTIFIER `-` IDENTIFIER),
        so reassemble them here. Returns the lower-cased name, or None if the
        current token can't start an attribute name. Does not advance on None.
        """
        tok = self._current()
        if tok.type not in (TokenType.IDENTIFIER,) + self._SOFT_KEYWORDS:
            return None
        parts = [str(self._advance().value)]
        while self._match(TokenType.OP_MINUS) and self._peek().type in (
            (TokenType.IDENTIFIER,) + self._SOFT_KEYWORDS
        ):
            self._advance()  # consume '-'
            parts.append(str(self._advance().value))
        return '-'.join(parts).lower()

    def _is_safe_attr_name(self, name):
        """Whether `name` is an allowed generic attribute (no on* handlers)."""
        if not name or name.startswith('on'):
            return False
        if name in ('style', 'class', 'id'):
            return False  # handled by dedicated parsing
        return name in self._SAFE_ATTR_NAMES or name.startswith('aria-') or name.startswith('data-')

    def _reject_unsafe_attr(self, name):
        """Raise a clear error for a disallowed `name "value"` attribute."""
        if name.startswith('on'):
            raise ParserError(
                f'Inline event handler "{name}" is not allowed for security. '
                f'Use a native event block instead of an on* attribute.',
                self._current().line,
            )
        raise ParserError(
            f'Unsupported attribute "{name}". Allowed: class, id, style, '
            f'aria-*, data-*, role, target, rel, title, lang, dir, tabindex, '
            f'download, hidden, draggable, spellcheck, translate.',
            self._current().line,
        )

    def _collect_inline_attrs(self, attrs, events=None):
        """Parse trailing `class`/`id`/`style`/safe attributes (and inline event
        sugar) on a one-line element (Link, Button) into the flat `attrs` dict.
        Stops at the end of the statement. `class` values merge; `style` collects
        a CSS string. If `events` is given, `on <event> <verb>` appends to it.
        """
        class_names = []
        css_decls = []
        while not self._match(TokenType.NEWLINE, TokenType.EOF, TokenType.DOT):
            if events is not None and self._match(TokenType.ON):
                events.append(self._parse_inline_event())
                continue
            if self._match(TokenType.CLASSNAME):
                self._advance()
                if self._match(TokenType.STRING):
                    class_names.append(self._advance().value)
                continue
            tok = self._current()
            if tok.type == TokenType.CLASS or (
                tok.type == TokenType.IDENTIFIER and tok.value.lower() == 'class'
            ):
                self._advance()
                if self._match(TokenType.STRING):
                    class_names.append(self._advance().value)
                continue
            if tok.type == TokenType.IDENTIFIER and tok.value.lower() == 'id':
                self._advance()
                if self._match(TokenType.STRING):
                    attrs['id'] = self._advance().value
                continue
            if self._match(TokenType.STYLE):
                self._advance()
                if self._match(TokenType.STRING):
                    css_decls.append(self._advance().value)
                continue
            saved = self.pos
            attr_name = self._read_attr_name()
            if attr_name is not None and self._match(TokenType.STRING):
                if not self._is_safe_attr_name(attr_name):
                    self._reject_unsafe_attr(attr_name)
                attrs[attr_name] = self._advance().value
                continue
            self.pos = saved
            break

        if class_names:
            existing = attrs.get('class')
            attrs['class'] = (f'{existing} ' if existing else '') + ' '.join(class_names)
        if css_decls:
            attrs['style'] = '; '.join(d.strip().rstrip(';').strip() for d in css_decls)

    @staticmethod
    def _split_inline_css(css):
        """Split an inline CSS string into (property, value) pairs."""
        pairs = []
        for decl in css.split(';'):
            decl = decl.strip()
            if not decl or ':' not in decl:
                continue
            prop, _, val = decl.partition(':')
            prop = prop.strip()
            val = val.strip()
            if prop and val:
                pairs.append((prop, val))
        return pairs

    # ─── Phase 4: Native event handlers ──────────────────────
    # Element-level `On <event> ... End` blocks and inline `on <event> <verb>`
    # sugar compile to CSP-safe generated JS (html_gen), never inline on*.
    _EVENT_NAMES = frozenset({'click', 'hover', 'reveal'})
    # Verb word (nested capitalised or inline 3rd-person) → action kind.
    _EVENT_VERBS = {
        'add': 'add_class',
        'adds': 'add_class',
        'remove': 'remove_class',
        'removes': 'remove_class',
        'toggle': 'toggle_class',
        'toggles': 'toggle_class',
        'navigate': 'navigate',
        'navigates': 'navigate',
        'scroll': 'scroll',
        'scrolls': 'scroll',
        'run': 'run',
        'runs': 'run',
    }
    _SELECTOR_ALLOWED = set(
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 #.>[]="\':_-'
    )

    @staticmethod
    def _event_class_ok(name):
        """Validate a single CSS class name."""
        if not name or not (name[0].isalpha() or name[0] in '-_'):
            return False
        return all(c.isalnum() or c in '-_' for c in name)

    def _event_selector_ok(self, sel):
        """Validate a CSS selector fragment (no braces/markup characters)."""
        return bool(sel) and all(c in self._SELECTOR_ALLOWED for c in sel)

    @staticmethod
    def _event_fn_ok(fn):
        """Validate a JS function identifier for the Run bridge."""
        if not fn or not (fn[0].isalpha() or fn[0] in '_$'):
            return False
        return all(c.isalnum() or c in '_$' for c in fn)

    def _read_event_name(self):
        """Read and validate the event name after `On`/`on`. Consumes it."""
        tok = self._current()
        if tok.type != TokenType.IDENTIFIER:
            raise ParserError('Expected an event name (click, hover, reveal) after "On".', tok.line)
        name = str(tok.value).lower()
        if name not in self._EVENT_NAMES:
            raise ParserError(f'Unknown event "{name}". Supported: click, hover, reveal.', tok.line)
        self._advance()
        return name

    def _read_event_verb(self):
        """Return the normalized action kind for the current verb token, or None.

        Consumes the verb token only on success. `Add` lexes as ADD_KW; all
        other verbs (and inline 3rd-person forms) lex as IDENTIFIER.
        """
        tok = self._current()
        if tok.type == TokenType.ADD_KW:
            word = 'add'
        elif tok.type == TokenType.IDENTIFIER:
            word = str(tok.value).lower()
        else:
            return None
        kind = self._EVENT_VERBS.get(word)
        if kind is None:
            return None
        self._advance()
        return kind

    def _parse_event_action(self):
        """Parse one action (class op / navigate / scroll / run). EventAction|None.

        Does not consume the trailing newline — the caller's loop handles line
        ends so this works for both nested blocks and inline single actions.
        """
        line = self._current().line
        kind = self._read_event_verb()
        if kind is None:
            return None
        data = {}
        if kind in ('add_class', 'remove_class', 'toggle_class'):
            # Optional `class` keyword (present in nested form, absent inline).
            cur = self._current()
            if cur.type == TokenType.CLASS or (
                cur.type == TokenType.IDENTIFIER and str(cur.value).lower() == 'class'
            ):
                self._advance()
            cls = self._expect(TokenType.STRING, 'Expected a class name string.').value
            if not self._event_class_ok(cls):
                raise ParserError(f'Invalid class name "{cls}".', line)
            data['class'] = cls
            if self._match(TokenType.ON):  # optional `on "#sel"` target
                self._advance()
                sel = self._expect(TokenType.STRING, 'Expected a selector after "on".').value
                if not self._event_selector_ok(sel):
                    raise ParserError(f'Invalid selector "{sel}".', line)
                data['selector'] = sel
        elif kind == 'navigate':
            if self._match(TokenType.TO):
                self._advance()
            data['url'] = self._expect(
                TokenType.STRING, 'Expected a URL after "Navigate to".'
            ).value
        elif kind == 'scroll':
            if self._match(TokenType.TO):
                self._advance()
            sel = self._expect(TokenType.STRING, 'Expected a selector after "Scroll to".').value
            if not self._event_selector_ok(sel):
                raise ParserError(f'Invalid selector "{sel}".', line)
            data['selector'] = sel
        elif kind == 'run':
            fn = self._expect(TokenType.STRING, 'Expected a function name after "Run".').value
            if not self._event_fn_ok(fn):
                raise ParserError(f'Invalid function name "{fn}".', line)
            data['fn'] = fn
        return ast.EventAction(kind, data, line)

    def _parse_event_handler(self):
        """Nested `On <event> ... End` block → EventHandler."""
        line = self._current().line
        self._advance()  # consume ON
        event = self._read_event_name()
        self._end_statement()
        actions = []
        while not self._match(TokenType.END, TokenType.EOF):
            self._skip_newlines()
            if self._match(TokenType.END, TokenType.EOF):
                break
            action = self._parse_event_action()
            if action is None:
                raise ParserError(
                    'Unknown action in event block. Use Add/Remove/Toggle class, '
                    'Navigate to, Scroll to, or Run.',
                    self._current().line,
                )
            actions.append(action)
        self._expect(TokenType.END, 'Expected "End" to close the "On" event block.')
        self._end_statement()
        return ast.EventHandler(event, actions, line)

    def _parse_inline_event(self):
        """Inline `on <event> <verb> ...` (single action) → EventHandler."""
        line = self._current().line
        self._advance()  # consume ON
        event = self._read_event_name()
        action = self._parse_event_action()
        if action is None:
            raise ParserError('Expected an action after the inline event.', line)
        return ast.EventHandler(event, [action], line)

    def _parse_styled_element(self, tag):
        """Div [with style "name"] [style "css"] [class "cls"] [id "myid"]
        [aria-* "v"] [data-* "v"] [role/target/rel/... "v"] ... End"""
        line = self._current().line
        self._advance()  # consume tag keyword

        styles = []
        class_names = []
        attributes = {}
        inline_styles = []
        events = []
        animate_name = None

        while not self._match(TokenType.NEWLINE, TokenType.EOF):
            # Inline event sugar: `on click toggles "x"` in the element header.
            if self._match(TokenType.ON):
                events.append(self._parse_inline_event())
                continue
            if self._match(TokenType.WITH):
                self._advance()
                if self._match(TokenType.STYLE):
                    self._advance()
                    if self._match(TokenType.STRING):
                        styles.append(self._advance().value)
                continue
            # Bare `style "css"` (NOT preceded by `with`) → inline styles.
            if self._match(TokenType.STYLE):
                self._advance()
                if self._match(TokenType.STRING):
                    css = self._advance().value
                    for prop, val in self._split_inline_css(css):
                        inline_styles.append(ast.StyleProperty(prop, val, line))
                continue
            if self._match(TokenType.CLASSNAME):
                self._advance()
                if self._match(TokenType.STRING):
                    class_names.append(self._advance().value)
                continue
            tok = self._current()
            if tok.type == TokenType.CLASS or (
                tok.type == TokenType.IDENTIFIER and tok.value.lower() == 'class'
            ):
                self._advance()
                if self._match(TokenType.STRING):
                    class_names.append(self._advance().value)
                continue
            if tok.type == TokenType.IDENTIFIER and tok.value.lower() == 'id':
                self._advance()
                if self._match(TokenType.STRING):
                    attributes['id'] = self._advance().value
                continue
            if self._match(TokenType.ANIMATE):
                self._advance()
                if self._match(TokenType.STRING):
                    animate_name = self._advance().value
                continue
            # Generic attribute: `name "value"` (incl. aria-*/data-*).
            saved = self.pos
            attr_name = self._read_attr_name()
            if attr_name is not None and self._match(TokenType.STRING):
                if not self._is_safe_attr_name(attr_name):
                    self._reject_unsafe_attr(attr_name)
                attributes[attr_name] = self._advance().value
                continue
            self.pos = saved  # not an attribute at all — stop parsing the header
            break

        self._end_statement()

        children = []
        while not self._match(TokenType.END, TokenType.EOF):
            self._skip_newlines()
            if self._match(TokenType.END, TokenType.EOF):
                break
            # Nested event block: `On click ... End` as an element child.
            if self._match(TokenType.ON):
                events.append(self._parse_event_handler())
                continue
            child = self._parse_element_or_statement()
            if child:
                children.append(child)

        self._expect(TokenType.END, f'Expected "End" to close {tag} block.')
        self._end_statement()

        if animate_name:
            attributes['data-animate'] = animate_name

        return ast.StyledElement(
            tag, styles, class_names, attributes, children, inline_styles, line, events
        )

    def _parse_layout_container(self, layout_type):
        """Flex direction "row" gap "16px" align "center" ... End
        Grid columns 3 gap "20px" ... End"""
        line = self._current().line
        self._advance()  # consume FLEX/GRID

        properties = {}
        while not self._match(TokenType.NEWLINE, TokenType.EOF):
            tok = self._current()
            if tok.type == TokenType.IDENTIFIER or tok.type in (
                TokenType.GRID,
                TokenType.FLEX,
                TokenType.ANIMATE,
            ):
                prop_name = tok.value.lower()
                self._advance()
                if self._match(TokenType.STRING):
                    properties[prop_name] = self._advance().value
                elif self._match(TokenType.NUMBER):
                    properties[prop_name] = self._advance().value
                else:
                    properties[prop_name] = 'true'
            else:
                break

        self._end_statement()

        children = []
        while not self._match(TokenType.END, TokenType.EOF):
            self._skip_newlines()
            if self._match(TokenType.END, TokenType.EOF):
                break
            child = self._parse_element_or_statement()
            if child:
                children.append(child)

        self._expect(TokenType.END, f'Expected "End" to close {layout_type} block.')
        self._end_statement()
        return ast.LayoutContainer(layout_type, properties, children, line)

    def _parse_component_def(self):
        """Component "Card" takes title, description ... End"""
        line = self._current().line
        self._advance()  # consume COMPONENT
        name_tok = self._expect(TokenType.STRING, 'Expected component name after "Component".')

        params = []
        if self._match(TokenType.TAKES):
            self._advance()
            params = self._parse_param_list()

        self._end_statement()

        body = []
        while not self._match(TokenType.END, TokenType.EOF):
            self._skip_newlines()
            if self._match(TokenType.END, TokenType.EOF):
                break
            stmt = self._parse_element_or_statement()
            if stmt:
                body.append(stmt)

        self._expect(TokenType.END, 'Expected "End" to close Component block.')
        self._end_statement()
        return ast.ComponentDef(name_tok.value, params, body, line)

    def _parse_responsive_block(self):
        """Responsive "mobile" ... End"""
        line = self._current().line
        self._advance()  # consume RESPONSIVE
        breakpoint = self._expect(TokenType.STRING, 'Expected breakpoint name after "Responsive".')
        self._end_statement()

        body = []
        while not self._match(TokenType.END, TokenType.EOF):
            self._skip_newlines()
            if self._match(TokenType.END, TokenType.EOF):
                break
            stmt = self._parse_element_or_statement()
            if stmt:
                body.append(stmt)

        self._expect(TokenType.END, 'Expected "End" to close Responsive block.')
        self._end_statement()
        return ast.ResponsiveBlock(breakpoint.value, body, line)

    def _parse_animate_def(self):
        """Animate "fadeIn"
            Duration "1s"
            Easing "ease-out"
            Keyframe 0
                Opacity "0"
            End
            Keyframe 100
                Opacity "1"
            End
        End"""
        line = self._current().line
        self._advance()  # consume ANIMATE
        name_tok = self._expect(TokenType.STRING, 'Expected animation name after "Animate".')
        self._end_statement()

        duration = None
        easing = None
        iteration = None
        keyframes = []

        while not self._match(TokenType.END, TokenType.EOF):
            self._skip_newlines()
            if self._match(TokenType.END, TokenType.EOF):
                break
            tok = self._current()
            if tok.type == TokenType.DURATION:
                self._advance()
                if self._match(TokenType.STRING):
                    duration = self._advance().value
                self._end_statement()
            elif tok.type == TokenType.EASING:
                self._advance()
                if self._match(TokenType.STRING):
                    easing = self._advance().value
                self._end_statement()
            elif tok.type == TokenType.IDENTIFIER and tok.value.lower() == 'iteration':
                self._advance()
                if self._match(TokenType.STRING):
                    iteration = self._advance().value
                elif self._match(TokenType.NUMBER):
                    iteration = str(self._advance().value)
                self._end_statement()
            elif tok.type == TokenType.KEYFRAME:
                keyframes.append(self._parse_keyframe_def())
            else:
                self._advance()
                self._end_statement()

        self._expect(TokenType.END, 'Expected "End" to close Animate block.')
        self._end_statement()
        return ast.AnimateDef(name_tok.value, duration, easing, iteration, keyframes, line)

    def _parse_keyframe_def(self):
        """Keyframe 0 ... End  or  Keyframe 100 ... End"""
        line = self._current().line
        self._advance()  # consume KEYFRAME
        if self._match(TokenType.NUMBER):
            percentage = self._advance().value
        else:
            percentage = 0
        self._end_statement()

        properties = []
        while not self._match(TokenType.END, TokenType.EOF):
            self._skip_newlines()
            if self._match(TokenType.END, TokenType.EOF):
                break
            prop = self._parse_style_property()
            if prop:
                properties.append(prop)

        self._expect(TokenType.END, 'Expected "End" to close Keyframe block.')
        self._end_statement()
        return ast.KeyframeDef(percentage, properties, line)

    def _parse_transition_def(self):
        """Transition "all" duration "0.3s" easing "ease" """
        line = self._current().line
        self._advance()  # consume TRANSITION_KW
        prop_name = 'all'
        if self._match(TokenType.STRING):
            prop_name = self._advance().value

        duration = None
        easing = None
        while not self._match(TokenType.NEWLINE, TokenType.EOF):
            tok = self._current()
            if tok.type == TokenType.DURATION:
                self._advance()
                if self._match(TokenType.STRING):
                    duration = self._advance().value
            elif tok.type == TokenType.EASING:
                self._advance()
                if self._match(TokenType.STRING):
                    easing = self._advance().value
            else:
                break

        self._end_statement()
        return ast.TransitionDef(prop_name, duration, easing, line)

    # ─── v6.1: 3D & Canvas System ─────────────────────────

    def _parse_scene_3d(self):
        """Scene "name" [width N] [height N] ... End"""
        line = self._current().line
        self._advance()  # consume SCENE
        name_tok = self._expect(TokenType.STRING, 'Expected scene name after "Scene".')

        width = 800
        height = 600
        while not self._match(TokenType.NEWLINE, TokenType.EOF):
            tok = self._current()
            if tok.type == TokenType.IDENTIFIER and tok.value.lower() == 'width':
                self._advance()
                if self._match(TokenType.NUMBER):
                    width = self._advance().value
            elif tok.type == TokenType.IDENTIFIER and tok.value.lower() == 'height':
                self._advance()
                if self._match(TokenType.NUMBER):
                    height = self._advance().value
            else:
                break
        self._end_statement()

        body = []
        while not self._match(TokenType.END, TokenType.EOF):
            self._skip_newlines()
            if self._match(TokenType.END, TokenType.EOF):
                break
            tok = self._current()
            if tok.type == TokenType.CAMERA_KW:
                body.append(self._parse_camera_setup())
            elif tok.type == TokenType.LIGHT:
                body.append(self._parse_light_setup())
            elif tok.type == TokenType.MESH:
                body.append(self._parse_mesh_add())
            else:
                stmt = self._parse_statement()
                if stmt:
                    body.append(stmt)

        self._expect(TokenType.END, 'Expected "End" to close Scene block.')
        self._end_statement()
        return ast.Scene3D(name_tok.value, width, height, body, line)

    def _parse_camera_setup(self):
        """Camera position 0, 5, 10 look_at 0, 0, 0 [fov 75]"""
        line = self._current().line
        self._advance()  # consume CAMERA_KW
        position = [0, 5, 10]
        look_at = [0, 0, 0]
        fov = 75

        while not self._match(TokenType.NEWLINE, TokenType.EOF):
            tok = self._current()
            if tok.type == TokenType.POSITION:
                self._advance()
                position = self._parse_number_list(3)
            elif tok.type == TokenType.IDENTIFIER and tok.value.lower() in (
                'look_at',
                'lookat',
                'target',
            ):
                self._advance()
                look_at = self._parse_number_list(3)
            elif tok.type == TokenType.IDENTIFIER and tok.value.lower() == 'fov':
                self._advance()
                if self._match(TokenType.NUMBER):
                    fov = self._advance().value
            else:
                break
        self._end_statement()
        return ast.CameraSetup(position, look_at, fov, line)

    def _parse_light_setup(self):
        """Light "ambient" [color "#fff"] [intensity 0.5] [position 0, 10, 0]"""
        line = self._current().line
        self._advance()  # consume LIGHT
        light_type = 'ambient'
        if self._match(TokenType.STRING):
            light_type = self._advance().value

        color = '#ffffff'
        intensity = 1.0
        position = None

        while not self._match(TokenType.NEWLINE, TokenType.EOF):
            tok = self._current()
            if tok.type == TokenType.IDENTIFIER and tok.value.lower() == 'color':
                self._advance()
                if self._match(TokenType.STRING):
                    color = self._advance().value
            elif tok.type == TokenType.IDENTIFIER and tok.value.lower() == 'intensity':
                self._advance()
                if self._match(TokenType.NUMBER):
                    intensity = self._advance().value
            elif tok.type == TokenType.POSITION:
                self._advance()
                position = self._parse_number_list(3)
            else:
                break
        self._end_statement()
        return ast.LightSetup(light_type, color, intensity, position, line)

    def _parse_mesh_add(self):
        """Mesh "cube" [position 0,0,0] [rotation 0,45,0] [scale 1,1,1] [color "#red"]"""
        line = self._current().line
        self._advance()  # consume MESH
        shape = 'cube'
        if self._match(TokenType.STRING):
            shape = self._advance().value

        name = None
        position = [0, 0, 0]
        rotation = [0, 0, 0]
        scale = [1, 1, 1]
        material = None
        color = None

        while not self._match(TokenType.NEWLINE, TokenType.EOF):
            tok = self._current()
            if tok.type == TokenType.IDENTIFIER and tok.value.lower() == 'name':
                self._advance()
                if self._match(TokenType.STRING):
                    name = self._advance().value
            elif tok.type == TokenType.POSITION:
                self._advance()
                position = self._parse_number_list(3)
            elif tok.type == TokenType.ROTATION:
                self._advance()
                rotation = self._parse_number_list(3)
            elif tok.type == TokenType.SCALE_KW:
                self._advance()
                scale = self._parse_number_list(3)
            elif tok.type == TokenType.MATERIAL:
                self._advance()
                if self._match(TokenType.STRING):
                    material = self._advance().value
            elif tok.type == TokenType.IDENTIFIER and tok.value.lower() == 'color':
                self._advance()
                if self._match(TokenType.STRING):
                    color = self._advance().value
            else:
                break
        self._end_statement()
        return ast.MeshAdd(shape, name, position, rotation, scale, material, color, line)

    def _parse_number_list(self, count):
        """Parse a comma-separated list of numbers (e.g., 0, 5, 10)."""
        numbers = []
        for i in range(count):
            if self._match(TokenType.NUMBER):
                numbers.append(self._advance().value)
            elif self._match(TokenType.OP_MINUS):
                self._advance()
                if self._match(TokenType.NUMBER):
                    numbers.append(-self._advance().value)
                else:
                    numbers.append(0)
            else:
                numbers.append(0)
            if i < count - 1:
                self._optional(TokenType.COMMA)
        return numbers

    def _parse_draw_command(self):
        """Draw "rect" x 10 y 10 width 100 height 50 fill "#ff0000" """
        line = self._current().line
        self._advance()  # consume DRAW
        shape = 'rect'
        if self._match(TokenType.STRING):
            shape = self._advance().value

        properties = {}
        while not self._match(TokenType.NEWLINE, TokenType.EOF):
            tok = self._current()
            if tok.type == TokenType.IDENTIFIER or tok.type in (
                TokenType.FILL,
                TokenType.STROKE,
                TokenType.POSITION,
                TokenType.SCALE_KW,
            ):
                prop_name = tok.value.lower()
                self._advance()
                if self._match(TokenType.STRING):
                    properties[prop_name] = self._advance().value
                elif self._match(TokenType.NUMBER):
                    properties[prop_name] = self._advance().value
                elif self._match(TokenType.OP_MINUS):
                    self._advance()
                    if self._match(TokenType.NUMBER):
                        properties[prop_name] = -self._advance().value
                else:
                    properties[prop_name] = True
            else:
                break

        self._end_statement()
        return ast.DrawCommand(shape, properties, line)
