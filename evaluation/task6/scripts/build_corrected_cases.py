"""Create versioned missing/conflict cases without modifying historical inputs."""
import argparse
import json
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CASES={
 'N03':dict(question='乙自己启用比不启用，第4周订单数期望相差多少？',
   delete='乙的同伴状态固定为甲=0、丙=0。',
   reply='本次比较中，乙的两个邻居甲和丙均不启用助手。',issue='比较时共同同伴状态尚未确定'),
 'N04':dict(question='在邻居甲丙都启用与都不启用之间，乙第4周平均订单数会增加多少？用前者减后者。',
   delete=None,reply='本次比较中，乙自己保持不启用助手。',issue='比较时乙自身处理状态尚未确定'),
 'N08':dict(question=None,delete='历史试点为分层固定名额：甲乙组成一层、丙丁组成一层，每层等概率抽中一店。',
   reply='历史试点为分层固定名额：甲乙一层、丙丁一层，每层等概率抽中一店。',issue='历史分配机制尚未提供'),
 'D12':dict(question=None,delete=None,
   replace=('研究者确认变量图：促销X→接触M→续费Y；潜在共同原因U同时影响X与Y，以X↔Y表示未观测混杂。',
            '研究者确认接触M→续费Y；潜在共同原因U同时影响X与Y，以X↔Y表示未观测混杂。'),
   reply='研究者确认促销X发生在接触M之前，变量图包含X→M；观察总体联合分布P(X,M,Y)可用。',
   issue='X→M是否成立以及观察总体联合分布均未确认'),
}


def build(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    (out/'materials').mkdir();(out/'references').mkdir()
    for scenario,spec in CASES.items():
        source=json.loads((ROOT/'materials'/('T6-'+scenario+'-changed.json')).read_text(encoding='utf8'))
        for variant in ('missing','conflict'):
            case=deepcopy(source);case['case_id']='T6v2-'+scenario+'-'+variant
            if variant=='missing':
                if spec['question'] is not None:case['business_question']=spec['question']
                if spec['delete']:
                    assert spec['delete'] in case['sources'][0]['text']
                    case['sources'][0]['text']=case['sources'][0]['text'].replace(spec['delete'],'')
                if spec.get('replace'):
                    old,new=spec['replace'];assert old in case['sources'][0]['text']
                    case['sources'][0]['text']=case['sources'][0]['text'].replace(old,new)
            ref=dict(case_id=case['case_id'],historical_source=source['case_id'],
                     expected_state='MISSING_STOP' if variant=='missing' else 'CONFLICT_STOP',
                     issue=spec['issue'],clarification_answer_prepared=spec['reply'],
                     reference_review='AUTHOR_DRAFT_NOT_INDEPENDENTLY_CERTIFIED',
                     warning='该参考只指导追问，不证明相关科学条件或最终识别结果。')
            for directory,value in [('materials',case),('references',ref)]:
                (out/directory/(case['case_id']+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('created',len(CASES)*2,'versioned materials and references')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();build(a.output)
