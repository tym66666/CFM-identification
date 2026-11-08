"""Plain-language entry point with unconfirmed interpretations held separately."""
from .business_shape_cli import main as _main
from .source_fact_formulator import SourceFactFormulator, render_source_fact_html


def main(argv=None):
    return _main(argv, flow_class=SourceFactFormulator, render=render_source_fact_html)


if __name__=='__main__':raise SystemExit(main())
