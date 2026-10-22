# Answers to docs/approval-request.md

(appended by the user; one line per decision)

The accepted vocabulary, so an answer is machine-readable rather than interpreted:

    2026-10-22 scope=shape
    2026-10-22 scope=function
    2026-10-22 ret=include
    2026-10-22 ret=exclude
    2026-10-22 sse=0.05
    2026-10-22 delegation=named

`scope=shape` is also the flag that makes a `scope = shape` row in `symbols/reviews.csv` legal at all:
without this line `tools/validate_functions.py` refuses such a row, and `tools/shape_approval.py`
refuses to cascade it. The review says what was reviewed; this file says the owner allowed it.
