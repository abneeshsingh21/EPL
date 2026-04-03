"""Pytest coverage for visibility modifier enforcement."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from epl.errors import RuntimeError as EPLRuntimeError
from epl.interpreter import Interpreter
from epl.lexer import Lexer
from epl.parser import Parser


class VisibilityAssertionError(Exception):
    """Assertion helper exception used by the legacy visibility checks."""


def run(src):
    lexer = Lexer(src)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    interpreter = Interpreter()
    interpreter.execute(program)
    return interpreter.output_lines


def assert_eq(actual, expected, message=""):
    if actual != expected:
        raise VisibilityAssertionError(f"Expected {expected!r}, got {actual!r}. {message}")


def assert_raises(src, error_substr):
    try:
        run(src)
    except EPLRuntimeError as exc:
        if error_substr.lower() not in str(exc).lower():
            raise VisibilityAssertionError(f"Expected '{error_substr}' in error, got: {exc}") from exc
        return
    except Exception as exc:
        if error_substr.lower() not in str(exc).lower():
            raise VisibilityAssertionError(
                f"Expected '{error_substr}' in error, got: {type(exc).__name__}: {exc}"
            ) from exc
        return
    raise VisibilityAssertionError(f"Expected error containing '{error_substr}' but no error was raised")


VISIBILITY_CASES = [
    (
        "private_prop_blocked_from_outside",
        lambda: assert_raises(
            'Class Vault\nPrivate Create code equal to 1234\nEnd\nCreate v equal to new Vault()\nPrint v.code',
            "private",
        ),
    ),
    (
        "private_prop_read_inside_method",
        lambda: assert_eq(
            run(
                'Class Vault\nPrivate Create code equal to 1234\nFunction get_code takes nothing\nReturn code\nEnd\nEnd\nCreate v equal to new Vault()\nPrint v.get_code()'
            ),
            ["1234"],
        ),
    ),
    (
        "private_prop_write_blocked_from_outside",
        lambda: assert_raises(
            'Class Vault\nPrivate Create code equal to 1234\nEnd\nCreate v equal to new Vault()\nv.code = 9999',
            "private",
        ),
    ),
    (
        "private_prop_set_inside_method",
        lambda: assert_eq(
            run(
                'Class Counter\nPrivate Create count equal to 0\nFunction increment takes nothing\nSet count to count + 1\nEnd\nFunction get takes nothing\nReturn count\nEnd\nEnd\nCreate c equal to new Counter()\nc.increment()\nc.increment()\nPrint c.get()'
            ),
            ["2"],
        ),
    ),
    (
        "multiple_private_props",
        lambda: assert_eq(
            run(
                'Class Pair\nPrivate Create left_val equal to "a"\nPrivate Create right_val equal to "b"\nFunction combine takes nothing\nReturn left_val + right_val\nEnd\nEnd\nCreate p equal to new Pair()\nPrint p.combine()'
            ),
            ["ab"],
        ),
    ),
    (
        "private_prop_not_accessible_from_other_class",
        lambda: assert_raises(
            'Class Secret\nPrivate Create data equal to 42\nEnd\nClass Spy\nFunction steal takes target\nReturn target.data\nEnd\nEnd\nCreate s equal to new Secret()\nCreate spy equal to new Spy()\nPrint spy.steal(s)',
            "private",
        ),
    ),
    (
        "private_method_blocked_from_outside",
        lambda: assert_raises(
            'Class Engine\nPrivate Function ignite takes nothing\nReturn "vroom"\nEnd\nEnd\nCreate e equal to new Engine()\nPrint e.ignite()',
            "private",
        ),
    ),
    (
        "private_method_callable_internally",
        lambda: assert_eq(
            run(
                'Class Engine\nPrivate Function ignite takes nothing\nReturn "vroom"\nEnd\nFunction start takes nothing\nReturn this.ignite()\nEnd\nEnd\nCreate e equal to new Engine()\nPrint e.start()'
            ),
            ["vroom"],
        ),
    ),
    (
        "private_method_chain_internal",
        lambda: assert_eq(
            run(
                'Class Math\nPrivate Function double takes n\nReturn n * 2\nEnd\nPrivate Function triple takes n\nReturn n * 3\nEnd\nFunction compute takes n\nReturn this.double(n) + this.triple(n)\nEnd\nEnd\nCreate m equal to new Math()\nPrint m.compute(5)'
            ),
            ["25"],
        ),
    ),
    (
        "private_init_still_works",
        lambda: assert_eq(
            run(
                'Class Box\nPrivate Create size equal to 0\nFunction init takes s\nSet size to s\nEnd\nFunction get_size takes nothing\nReturn size\nEnd\nEnd\nCreate b equal to new Box(10)\nPrint b.get_size()'
            ),
            ["10"],
        ),
    ),
    (
        "protected_prop_blocked_from_outside",
        lambda: assert_raises(
            'Class Animal\nProtected Create species equal to "unknown"\nEnd\nCreate obj equal to new Animal()\nPrint obj.species',
            "protected",
        ),
    ),
    (
        "protected_prop_accessible_in_subclass",
        lambda: assert_eq(
            run(
                'Class Animal\nProtected Create species equal to "unknown"\nEnd\nClass Dog extends Animal\nFunction get_species takes nothing\nReturn species\nEnd\nEnd\nCreate obj equal to new Dog()\nPrint obj.get_species()'
            ),
            ["unknown"],
        ),
    ),
    (
        "protected_prop_set_in_subclass",
        lambda: assert_eq(
            run(
                'Class Animal\nProtected Create species equal to "unknown"\nEnd\nClass Cat extends Animal\nFunction init takes nothing\nSet species to "feline"\nEnd\nFunction get_species takes nothing\nReturn species\nEnd\nEnd\nCreate obj equal to new Cat()\nPrint obj.get_species()'
            ),
            ["feline"],
        ),
    ),
    (
        "protected_prop_deep_inheritance",
        lambda: assert_eq(
            run(
                'Class Base\nProtected Create val equal to 100\nEnd\nClass Mid extends Base\nEnd\nClass Leaf extends Mid\nFunction get_val takes nothing\nReturn val\nEnd\nEnd\nCreate obj equal to new Leaf()\nPrint obj.get_val()'
            ),
            ["100"],
        ),
    ),
    (
        "protected_method_blocked_from_outside",
        lambda: assert_raises(
            'Class Base\nProtected Function helper takes nothing\nReturn 42\nEnd\nEnd\nCreate obj equal to new Base()\nPrint obj.helper()',
            "protected",
        ),
    ),
    (
        "protected_method_callable_from_subclass",
        lambda: assert_eq(
            run(
                'Class Base\nProtected Function helper takes nothing\nReturn 42\nEnd\nEnd\nClass Child extends Base\nFunction compute takes nothing\nReturn this.helper()\nEnd\nEnd\nCreate obj equal to new Child()\nPrint obj.compute()'
            ),
            ["42"],
        ),
    ),
    (
        "explicit_public_prop",
        lambda: assert_eq(
            run('Class Person\nPublic Create nickname equal to "Joe"\nEnd\nCreate obj equal to new Person()\nPrint obj.nickname'),
            ["Joe"],
        ),
    ),
    (
        "explicit_public_method",
        lambda: assert_eq(
            run('Class Greeter\nPublic Function greet takes nothing\nReturn "hello"\nEnd\nEnd\nCreate obj equal to new Greeter()\nPrint obj.greet()'),
            ["hello"],
        ),
    ),
    (
        "default_is_public_prop",
        lambda: assert_eq(
            run('Class Open\nCreate field equal to "visible"\nEnd\nCreate obj equal to new Open()\nPrint obj.field'),
            ["visible"],
        ),
    ),
    (
        "default_is_public_method",
        lambda: assert_eq(
            run('Class Open\nFunction method takes nothing\nReturn "ok"\nEnd\nEnd\nCreate obj equal to new Open()\nPrint obj.method()'),
            ["ok"],
        ),
    ),
    (
        "public_prop_set_from_outside",
        lambda: assert_eq(
            run('Class Mutable\nPublic Create val equal to 1\nEnd\nCreate obj equal to new Mutable()\nobj.val = 99\nPrint obj.val'),
            ["99"],
        ),
    ),
    (
        "mixed_public_private_props",
        lambda: assert_eq(
            run(
                'Class Account\nPublic Create owner equal to "Alice"\nPrivate Create balance equal to 1000\nFunction get_balance takes nothing\nReturn balance\nEnd\nEnd\nCreate acc equal to new Account()\nPrint acc.owner\nPrint acc.get_balance()'
            ),
            ["Alice", "1000"],
        ),
    ),
    (
        "mixed_public_private_methods",
        lambda: assert_eq(
            run(
                'Class Service\nPrivate Function validate takes nothing\nReturn true\nEnd\nPublic Function process takes nothing\nIf this.validate()\nReturn "done"\nEnd\nReturn "fail"\nEnd\nEnd\nCreate svc equal to new Service()\nPrint svc.process()'
            ),
            ["done"],
        ),
    ),
    (
        "mixed_private_prop_public_method_blocks",
        lambda: assert_raises(
            'Class Safe\nPrivate Create pin equal to 1234\nPublic Function check takes guess\nReturn guess == pin\nEnd\nEnd\nCreate obj equal to new Safe()\nPrint obj.pin',
            "private",
        ),
    ),
    (
        "inherited_public_stays_public",
        lambda: assert_eq(
            run('Class Base\nPublic Create tag equal to "base"\nEnd\nClass Child extends Base\nEnd\nCreate obj equal to new Child()\nPrint obj.tag'),
            ["base"],
        ),
    ),
    (
        "inherited_private_stays_private",
        lambda: assert_raises(
            'Class Base\nPrivate Create secret equal to "hidden"\nEnd\nClass Child extends Base\nEnd\nCreate obj equal to new Child()\nPrint obj.secret',
            "private",
        ),
    ),
    (
        "this_access_to_private_prop",
        lambda: assert_eq(
            run('Class Obj\nPrivate Create val equal to 7\nFunction get_val takes nothing\nReturn this.val\nEnd\nEnd\nCreate obj equal to new Obj()\nPrint obj.get_val()'),
            ["7"],
        ),
    ),
    (
        "this_set_private_prop",
        lambda: assert_eq(
            run(
                'Class Obj\nPrivate Create val equal to 0\nFunction set_val takes v\nSet val to v\nEnd\nFunction get_val takes nothing\nReturn val\nEnd\nEnd\nCreate obj equal to new Obj()\nobj.set_val(42)\nPrint obj.get_val()'
            ),
            ["42"],
        ),
    ),
    (
        "private_method_with_private_prop",
        lambda: assert_eq(
            run(
                'Class Calc\nPrivate Create state equal to 0\nPrivate Function compute takes n\nReturn n * 2\nEnd\nFunction run_calc takes n\nReturn this.compute(n)\nEnd\nEnd\nCreate calc equal to new Calc()\nPrint calc.run_calc(5)'
            ),
            ["10"],
        ),
    ),
    (
        "no_visibility_on_builtin_methods",
        lambda: assert_eq(
            run('Class Holder\nCreate items equal to [1, 2, 3]\nEnd\nCreate obj equal to new Holder()\nPrint obj.items.length'),
            ["3"],
        ),
    ),
    (
        "multiple_instances_same_visibility",
        lambda: assert_eq(
            run(
                'Class Thing\nPrivate Create id_val equal to 0\nFunction init takes n\nSet id_val to n\nEnd\nFunction get_id takes nothing\nReturn id_val\nEnd\nEnd\nCreate t1 equal to new Thing(1)\nCreate t2 equal to new Thing(2)\nPrint t1.get_id()\nPrint t2.get_id()'
            ),
            ["1", "2"],
        ),
    ),
]


@pytest.mark.parametrize(("name", "check_fn"), VISIBILITY_CASES, ids=[name for name, _ in VISIBILITY_CASES])
def test_visibility_cases(name, check_fn):
    check_fn()
