"""Safety boundary for the student's hand-authored reference examples."""
from pathlib import Path

MODE = "HAND_AUTHORED_REFERENCE_FIXTURE"


def arguments(parser):
    parser.add_argument("--reference-fixture", action="store_true",
                        help="Run a hand-authored reference, NOT a business/LLM test.")
    parser.add_argument("--output", type=Path, required=True,
                        help="New output directory outside the source tree.")


def output(args, source_root):
    if not args.reference_fixture:
        raise ValueError("REFERENCE_FIXTURE_OPT_IN_REQUIRED")
    destination = args.output.resolve()
    root = Path(source_root).resolve()
    if destination == root or root in destination.parents:
        raise ValueError("OUTPUT_MUST_BE_OUTSIDE_SOURCE")
    if destination.exists():
        raise ValueError("NEW_OUTPUT_DIRECTORY_REQUIRED")
    destination.mkdir(parents=True)
    return destination
