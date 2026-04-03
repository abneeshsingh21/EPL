# epl-test

Supported EPL testing facade package.

## Install

```bash
epl install epl-test
```

## Use

```epl
Import "epl-test"

Call test("math works", Function()
    Call expect_equal(1 + 1, 2, "basic arithmetic")
End)

Call test_summary()
```

## Included Surface

- `test`
- `expect_equal`
- `expect_true`
- `expect_false`
- `expect_error`
- `test_summary`
