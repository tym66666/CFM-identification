"""Independent exact enumeration for the seven-node pilot's reference model.

Does not import the project solver or verifier. This checks the stated finite
mean-box model, not model-generated facts or real scientific assumptions.
"""
from fractions import Fraction
from itertools import combinations
import json


def run():
    nodes=range(7)
    assignments=[frozenset(x) for x in combinations(nodes,3)]
    assert len(assignments)==35
    def signature(i,a):
        neighbors=range(1,7) if i==0 else (0,)
        exposed=sum(j in a for j in neighbors)
        size=6 if i==0 else 1
        return (int(i in a),int(2*exposed>size))
    target=frozenset(nodes)
    target_signature=[signature(i,target) for i in nodes]
    support=[sum(signature(i,a)==target_signature[i] for a in assignments) for i in nodes]
    # The original pilot's information lists target cells for all leaves, 1/2.
    # The center's target cell is unsupported and constrained only to [0,1].
    assert support[0]==0 and all(v>0 for v in support[1:])
    lower=sum([Fraction(0)]+[Fraction(1,2)]*6)/7
    upper=sum([Fraction(1)]+[Fraction(1,2)]*6)/7
    assert lower==Fraction(3,7) and upper==Fraction(4,7)
    return {'assignments':len(assignments),'target_signatures':target_signature,
            'target_support_counts':support,'lower':str(lower),'upper':str(upper),
            'non_point':lower<upper,'reference_scope':'stated seven-node finite mean-box model'}


if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
