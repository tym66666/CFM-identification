"""Optional two-call ordinary-language intake with bounded source review."""
from .business_shape_cli import main as _main
from .literal_grounding import QuoteReviewedIntake, render_grounding_html, TwoResponseMock


def main(argv=None):
    return _main(argv, flow_class=QuoteReviewedIntake, render=render_grounding_html, mock_factory=TwoResponseMock,
        description='普通话问题与附件 → 业务提取及原文核对 → 中文理解稿（两次模型调用）')


if __name__=='__main__':raise SystemExit(main())
