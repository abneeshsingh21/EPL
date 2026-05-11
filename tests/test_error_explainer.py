"""Tests for the epl.error_explainer module (PR #3).

Covers:
- Pattern matching for NameError, TypeError, ParserError, RuntimeError
- Foreign keyword detection (Python/JS syntax)
- "Did you mean?" suggestions
- Block analysis for missing End
- Formatter output structure
"""

import unittest


class TestErrorExplanationDataclass(unittest.TestCase):
    """Verify the ErrorExplanation dataclass structure."""

    def test_defaults(self):
        from epl.error_explainer import ErrorExplanation

        exp = ErrorExplanation(
            error_type='NameError',
            error_code='E0500',
            message='test',
            line=1,
            source_line='test line',
            what_went_wrong='bad',
            how_to_fix='fix it',
            corrected_code='',
        )
        self.assertEqual(exp.ai_explanation, '')
        self.assertEqual(exp.category, '')
        self.assertEqual(exp.confidence, 1.0)

    def test_all_fields_set(self):
        from epl.error_explainer import ErrorExplanation

        exp = ErrorExplanation(
            error_type='ParserError',
            error_code='E0200',
            message='msg',
            line=5,
            source_line='bad line',
            what_went_wrong='w',
            how_to_fix='h',
            corrected_code='c',
            ai_explanation='ai',
            category='syntax',
            confidence=0.9,
        )
        self.assertEqual(exp.error_type, 'ParserError')
        self.assertEqual(exp.confidence, 0.9)


class TestExplainUndefinedVariable(unittest.TestCase):
    """Test pattern matching for undefined variables."""

    def test_undefined_variable_gives_suggestion(self):
        from epl.error_explainer import explain
        from epl.errors import NameError, set_source_context

        source = 'Create counter equal to 0\nSay cunter\n'
        set_source_context(source, '<test>')
        err = NameError("Undefined variable 'cunter'", line=2)
        exp = explain(err, source=source)
        self.assertIn('cunter', exp.what_went_wrong)
        self.assertEqual(exp.category, 'name')
        self.assertGreater(exp.confidence, 0.5)

    def test_undefined_variable_no_match(self):
        from epl.error_explainer import explain
        from epl.errors import NameError, set_source_context

        source = 'Say xyzzy\n'
        set_source_context(source, '<test>')
        err = NameError("Undefined variable 'xyzzy'", line=1)
        exp = explain(err, source=source)
        self.assertIn('xyzzy', exp.what_went_wrong)
        self.assertIn('Create', exp.how_to_fix)


class TestExplainUndefinedFunction(unittest.TestCase):
    """Test pattern matching for undefined functions."""

    def test_similar_function_name(self):
        from epl.error_explainer import explain
        from epl.errors import NameError, set_source_context

        source = 'Say lenght("hello")\n'
        set_source_context(source, '<test>')
        err = NameError("Undefined function 'lenght'", line=1)
        exp = explain(err, source=source)
        self.assertIn('lenght', exp.what_went_wrong)
        self.assertEqual(exp.category, 'name')


class TestExplainTypeErrors(unittest.TestCase):
    """Test type mismatch pattern matching."""

    def test_type_mismatch(self):
        from epl.error_explainer import explain
        from epl.errors import TypeError

        err = TypeError('Cannot add string and integer', line=3)
        exp = explain(err, source='Create x equal to "hi" + 5\n')
        self.assertIn('incompatible types', exp.what_went_wrong)
        self.assertEqual(exp.category, 'type')

    def test_type_cannot_compare(self):
        from epl.error_explainer import explain
        from epl.errors import TypeError

        err = TypeError('Cannot compare these values', line=1)
        exp = explain(err)
        self.assertIn('incompatible', exp.what_went_wrong)


class TestExplainParserErrors(unittest.TestCase):
    """Test parser error patterns."""

    def test_missing_end(self):
        from epl.error_explainer import explain
        from epl.errors import ParserError, set_source_context

        source = 'Function greet\n    Say "Hello"\n'
        set_source_context(source, '<test>')
        err = ParserError('Expected "End"', line=2)
        exp = explain(err, source=source)
        self.assertIn('Function', exp.what_went_wrong)
        self.assertEqual(exp.category, 'syntax')

    def test_unexpected_python_print(self):
        from epl.error_explainer import explain
        from epl.errors import ParserError

        err = ParserError("Unexpected token 'print'", line=1)
        exp = explain(err, source='print("hello")\n')
        self.assertIn('Python', exp.what_went_wrong)
        self.assertIn('Say', exp.how_to_fix)


class TestExplainRuntimeErrors(unittest.TestCase):
    """Test runtime error patterns."""

    def test_divide_by_zero(self):
        from epl.error_explainer import explain
        from epl.errors import RuntimeError

        err = RuntimeError('Division by zero', line=1)
        exp = explain(err)
        self.assertIn('zero', exp.what_went_wrong)
        self.assertEqual(exp.category, 'runtime')

    def test_index_out_of_range(self):
        from epl.error_explainer import explain
        from epl.errors import RuntimeError

        err = RuntimeError('Index out of range', line=1)
        exp = explain(err)
        self.assertIn('position', exp.what_went_wrong)
        self.assertEqual(exp.category, 'index')

    def test_max_recursion(self):
        from epl.error_explainer import explain
        from epl.errors import RuntimeError

        err = RuntimeError('Maximum recursion depth exceeded', line=1)
        exp = explain(err)
        self.assertIn('calling itself', exp.what_went_wrong)

    def test_key_not_found(self):
        from epl.error_explainer import explain
        from epl.errors import RuntimeError

        err = RuntimeError("Key not found: 'age'", line=1)
        exp = explain(err)
        self.assertIn('Map', exp.what_went_wrong)


class TestExplainForeignKeywords(unittest.TestCase):
    """Test detection of Python/JS syntax."""

    def test_unexpected_def(self):
        from epl.error_explainer import explain
        from epl.errors import ParserError

        err = ParserError("Unexpected token 'def'", line=1)
        exp = explain(err, source='def greet():\n')
        self.assertIn('Python', exp.what_went_wrong)
        self.assertIn('Function', exp.how_to_fix)

    def test_unexpected_for(self):
        from epl.error_explainer import explain
        from epl.errors import ParserError

        err = ParserError("Unexpected token 'for'", line=1)
        exp = explain(err, source='for i in range(10):\n')
        self.assertIn('EPL syntax', exp.what_went_wrong)


class TestFormatExplanation(unittest.TestCase):
    """Test the terminal formatter."""

    def test_format_contains_key_sections(self):
        from epl.error_explainer import ErrorExplanation, format_explanation

        exp = ErrorExplanation(
            error_type='NameError',
            error_code='E0500',
            message='test',
            line=1,
            source_line='test line',
            what_went_wrong='Something went wrong',
            how_to_fix='Fix it like this',
            corrected_code='fixed code',
        )
        output = format_explanation(exp, color=False)
        self.assertIn('Something went wrong', output)
        self.assertIn('Fix it like this', output)
        self.assertIn('fixed code', output)

    def test_format_with_ai(self):
        from epl.error_explainer import ErrorExplanation, format_explanation

        exp = ErrorExplanation(
            error_type='NameError',
            error_code='E0500',
            message='test',
            line=1,
            source_line='test line',
            what_went_wrong='w',
            how_to_fix='h',
            corrected_code='',
            ai_explanation='AI says: check your variables',
        )
        output = format_explanation(exp, color=False)
        self.assertIn('AI says', output)


class TestToContextDict(unittest.TestCase):
    """Test the to_context_dict extension on EPLError."""

    def test_context_dict_includes_source(self):
        from epl.errors import NameError, set_source_context

        source = 'Line one\nLine two\nLine three\n'
        set_source_context(source, '<test>')
        err = NameError('test', line=2)
        d = err.to_context_dict()
        self.assertEqual(d['source_line'], 'Line two')
        self.assertIn('context', d)
        self.assertIn('Line two', d['context'])

    def test_context_dict_no_source(self):
        from epl.errors import NameError, set_source_context

        set_source_context('', '<test>')
        err = NameError('test', line=1)
        d = err.to_context_dict()
        self.assertNotIn('source_line', d)


class TestExplainImportError(unittest.TestCase):
    """Test import error pattern matching."""

    def test_import_not_found(self):
        from epl.error_explainer import explain
        from epl.errors import ImportError

        err = ImportError("Cannot find module 'mylib'", line=1)
        exp = explain(err)
        self.assertIn('module', exp.what_went_wrong.lower())
        self.assertEqual(exp.category, 'import')


if __name__ == '__main__':
    unittest.main()
