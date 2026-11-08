from .business_shape_cli import main as shared_main
from .semantic_roles import ScopedRoleFormulator,render_role_html

def main(argv=None):
    return shared_main(argv,flow_class=ScopedRoleFormulator,render=render_role_html,
        description='普通话问题与附件 → 区分事实职责并复核人群与情形 → 中文理解稿（一次模型调用）')

if __name__=='__main__':raise SystemExit(main())
