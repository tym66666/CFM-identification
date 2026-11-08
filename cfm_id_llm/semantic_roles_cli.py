"""Opt-in ordinary-language intake with one semantic-role extraction call."""
from .business_shape_cli import main as shared_main
from .semantic_roles_base import SemanticRoleFormulator, render_role_html

def main(argv=None):
    return shared_main(argv, flow_class=SemanticRoleFormulator, render=render_role_html,
        description='普通话问题与附件 → 区分背景、条件、汇总规则 → 中文理解稿（一次模型调用）')

if __name__ == '__main__':
    raise SystemExit(main())
