"""Versioned candidate prompt clarification; v035 frozen results remain unchanged."""
from .business_candidate_base import evaluate_with_candidates as previous

VERSION = "business-candidate-v0.35.1"
ADDITIONAL_RULES = """
补充：以下是已审核输入字段的解释规则，不是本题参考答案。
1. target_unit_weights与target_assignment是已经审核的精确目标。按给定权重写目标，不再把已明确的等权/政策名单列为TARGET_DEFINITION缺失。
2. admitted的known_assignment_law表示给定的条件分配律；full_vector_randomization表示给定W时完整分配向量与潜在结果表独立；consistency表示观测结果Y_i^obs=Y_i(Z)。不要将已批准的同一假设重新列为additional_requirements。
3. consistency不等于把潜在结果写成随机变量等式Y_i(a)=Y_i|Z=a。即使已有随机化，从观测总体律取E[Y_i^obs|Z=a,W]也需要相应支持。零概率事件上的条件量不能直接从观测律读取。
4. NODE_FULL_LAW是已声明的每个节点结果与完整分配向量的总体观测律信息，不是所有潜在结果，不是跨节点完整联合律，也不授权对零概率分配任意条件化。
5. 根据明确的分配规则分析结构支持。区分“设计概率为零”和“有限样本中碰巧没有出现”，不要把前者改成再查看样本记录即可解决的问题。
6. 新的均值暴露充分性、无干扰或函数形式限制必须作为额外假设；暴露映射定义本身不能批准它们。只求均值时，避免不加说明地要求完整分布充分性这种更强条件。
7. 优先给出具体且可核查的分析。可以回答无法确定；不要用重新确认已给出的条件填充答案。NOT_POINT必须构造具体的两个世界并说明观测律相同、目标不同；Core的UNSUPPORTED本身不能证明它。
8. 无论建议多具体，数学正确性仍未验证，禁止证书或认证措辞。
"""


def evaluate_with_candidates(value, raw, packet, *, provider=None, **kwargs):
    class ExplainedProvider:
        name = provider.name if provider else "NOT_CONFIGURED"

        def generate_json(self, *, system_prompt, user_prompt):
            return provider.generate_json(system_prompt=system_prompt + ADDITIONAL_RULES,
                                          user_prompt=user_prompt)
    result = previous(value, raw, packet, provider=ExplainedProvider() if provider else None, **kwargs)
    result.update(version=VERSION, candidate_prompt_version=VERSION)
    return result
