from epl.cli import _parse_epl_program

code = """
If x > 10 then
    label = "big"
Otherwise
    label = "small"
End
"""
try:
    _parse_epl_program(code, 'test.epl')
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
