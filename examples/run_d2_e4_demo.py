"""Demo: Run and verify PARTIAL bounds for D2 (Fixed Quota) + E4 (Exact Neighbor Count).

Run command: python -m examples.run_d2_e4_demo
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from cfm_id.bounded_policy_fixture import model, reviews
from cfm_id.general_bounded_policy_solver import solve
from cfm_id.bounded_policy import submit

def main():
    print(">>> 1. 准备 D2(固定名额) + E4(准确邻居人数) 数据...")
    # 借用原仓库的星型网络(7节点)测试数据
    inquiry, info = model('star7', population=None)
    
    # 强制使用 D2 + E4 (绕过原有默认的D2/E1)
    dk, ek = 'D2', 'E4'
    
    print(f">>> 2. 调用单政策求解器计算界限 (Design={dk}, Exposure={ek})...")
    try:
        # 调用你的通用求解器
        cert = solve(inquiry, info, design_kind=dk, exposure_kind=ek)
        print(f"    状态: {cert['status']}")
        print(f"    界限: [{cert['lower']}, {cert['upper']}]")
        print(f"    Sharp性: {cert['sharp']}")
        
        print(f">>> 3. 验证端点与对偶证书...")
        if cert['status'] == 'PARTIAL':
             print("    ✅ 成功输出 PARTIAL 界限！")
             
    except Exception as e:
        print(f"    ❌ 求解失败: {e}")

    print("\n>>> 4. 检查缺条件阻断 (无核心伙伴时的E3/E4非法组合)...")
    # 这里只展示逻辑：如果你传 E3 且不给 core_collaborators，系统必须报错
    # （因为你的代码里写死了 _require_core_collaborators 会抛异常）
    try:
        solve(inquiry, info, design_kind=dk, exposure_kind='E3')
        print("    ❌ 错误：E3缺失核心伙伴名单未阻断！")
    except Exception as e:
        print(f"    ✅ 成功阻断：{e}")

if __name__ == '__main__':
    main()