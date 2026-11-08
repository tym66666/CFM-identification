from .business_shape_cli import main as shared_main
from .semantic_roles_clarified import ClarifiedRoleFormulator,render_role_html

def main(argv=None):
    return shared_main(argv,flow_class=ClarifiedRoleFormulator,render=render_role_html,
        description='普通话问题与附件 → 明确字段职责并复核范围歧义 → 中文理解稿（一次模型调用）')

if __name__=='__main__':raise SystemExit(main())
