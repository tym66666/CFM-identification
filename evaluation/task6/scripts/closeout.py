"""Offline Task 6 closeout. Reads existing evidence; never calls a model or approves a review.

python -m evaluation.task6.scripts.closeout --output outputs/task6_closeout
"""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(value):
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def closeout(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    groups, errors, integrity, review_summary, files = [], [], [], {}, []
    manifests = []
    split_cases = {}
    for name, review_file in (
        ('task6_dev_final_002', 'review_assisted.csv'),
        ('task6_holdout_final_001', 'Task6_holdout32_pre_review.csv'),
    ):
        folder = REPO / 'outputs' / name
        manifest = read(folder / 'manifest.json')
        runs = read(folder / 'runs.json')
        manifests.append(manifest)
        split = manifest['set']
        split_cases[split] = set(manifest['source_material_hashes'])
        expected_pairs = {(cid, profile, rep) for cid in split_cases[split]
            for profile in manifest['profiles'] for rep in range(1, manifest['repeats'] + 1)}
        actual_pairs = {(r['case_id'], r['profile'], r['repeat']) for r in runs}
        if expected_pairs != actual_pairs or len(actual_pairs) != len(runs):
            integrity.append(f'{split}: paired design missing or duplicated records')
        if len(runs) != manifest['calls_planned']:
            integrity.append(f'{split}: planned/recorded attempt count mismatch')
        for filename in ('manifest.json', 'runs.json', review_file):
            path = folder / filename
            files.append({'path':path.relative_to(REPO).as_posix(),
                          'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        for cid, expected in manifest['source_material_hashes'].items():
            if digest(read(ROOT / 'materials' / (cid + '.json'))) != expected:
                integrity.append(f'{split}: material changed: {cid}')
        indexed = {r['id']: r for r in runs}
        if len(indexed) != len(runs):
            integrity.append(f'{split}: duplicate run IDs')
        private_results = list((folder / 'private').glob('*/result.json'))
        if len(private_results) != len(runs):
            integrity.append(f'{split}: private record count mismatch')
        for path in private_results:
            record = read(path)
            if indexed.get(record['id']) != record:
                integrity.append(f'{split}: public/private result mismatch: {record["id"]}')
            req = read(path.parent / 'request.json')
            for field, hash_field in (('system_prompt','system_prompt_sha256'),
                                      ('user_prompt','user_prompt_sha256')):
                if digest(req[field]) != record[hash_field]:
                    integrity.append(f'{split}: prompt hash mismatch: {record["id"]}')
            if req['request_sha256'] != record['request_sha256']:
                integrity.append(f'{split}: request binding mismatch: {record["id"]}')
            if record['raw_response_saved']:
                raw_path = path.parent / 'raw_response.json'
                if raw_path.exists():
                    read(raw_path)
                else:
                    integrity.append(f'{split}: raw_response_saved=true but file absent: {record["id"]}')
            # Hashes allow restricted evidence verification without publishing its contents.
            for evidence in path.parent.glob('*.json'):
                files.append({'path':evidence.relative_to(REPO).as_posix(),
                              'sha256':hashlib.sha256(evidence.read_bytes()).hexdigest()})
        with (folder / review_file).open(encoding='utf-8-sig', newline='') as stream:
            reviews = list(csv.DictReader(stream))
        review_summary[split] = {
            'status':'AI_ASSISTED_PRELIMINARY_NOT_INDEPENDENT_HUMAN_REVIEW',
            'rows':len(reviews), 'reviewer_labels':dict(Counter(r['reviewer_id'] for r in reviews)),
            'judgments':dict(Counter(r['judgment'] for r in reviews)),
        }
        for profile in ('prompt_only', 'prompt_plus_skill'):
            selected = [r for r in runs if r['profile'] == profile]
            repeats = []
            for rep in sorted({r['repeat'] for r in selected}):
                batch = [r for r in selected if r['repeat'] == rep]
                repeats.append({'repeat':rep, 'attempted':len(batch),
                                'parsed':sum(bool(r['format_parse_success']) for r in batch)})
            groups.append(dict(split=split, profile=profile, attempted=len(selected),
                transport_calls=sum(r['provider_diagnostics'].get('transport_calls',0) for r in selected),
                responses=sum(bool(r['raw_response_saved']) for r in selected),
                parsed=sum(bool(r['format_parse_success']) for r in selected),
                prompt_tokens=sum(r['usage'].get('prompt_tokens',0) for r in selected),
                completion_tokens=sum(r['usage'].get('completion_tokens',0) for r in selected),
                repeats=repeats,
                semantic_accuracy=None, missing_detection_accuracy=None,
                first_pass_full_chain_accuracy=None, wrong_certification_rate=None))
        for r in runs:
            if not r['format_parse_success']:
                errors.append({'split':split, 'case_id':r['case_id'], 'profile':r['profile'],
                    'repeat':r['repeat'], 'reason':r.get('wire_reason'), 'state':r['wire_state']})
    if split_cases['dev'] & split_cases['holdout']:
        integrity.append('development/holdout overlap')
    for key in ('git_head','model','profiles','skill_manifest','original_reading_config',
                'timeout','max_tokens','thinking','json_mode','repeats'):
        if manifests[0][key] != manifests[1][key]:
            integrity.append(f'configuration mismatch between splits: {key}')
    chain_dir = REPO / 'outputs/task6_n01_chain/full'
    plan = read(chain_dir / 'plan.json')
    chain_diag = read(chain_dir / 'fact_call_diagnostics.json')
    chain = {key:plan.get(key) for key in ('state','reason_code','backend_called','certificate')}
    chain['independent_approval_verified'] = False
    chain['first_answer_preserved'] = (chain_dir / 'fact_candidate_original.json').exists()
    chain['manually_modified_candidate_exists'] = (chain_dir / 'fact_candidate_reviewed.json').exists()
    chain['execution_result_exists'] = (chain_dir / 'execution_result.json').exists()
    chain['usage'] = chain_diag['usage']
    # Historic scores contain assisted labels under human_* names. Never promote them here.
    result = dict(scope='Existing 96 A0 attempts plus one separate N01 fact call',
        model=manifests[0]['model'], git_head=manifests[0]['git_head'],
        skill=manifests[0]['skill_manifest'], groups=groups, errors=errors,
        review_status=review_summary, n01_chain=chain,
        integrity_issues=integrity, new_api_calls=0,
        independent_reference_review='PENDING',
        holdout_blindness='NOT_PROVEN_BY_HASHES; existing holdout pre-review is now seen',
        configuration_recommendation='KEEP_EXISTING_DEFAULT; insufficient independent semantic evidence')
    write(output / 'summary.json', result)
    write(output / 'evidence_hashes.json', files)
    # Public configuration snapshot is allowlisted; raw prompts/responses remain private.
    write(output / 'experiment_config.json', {k:manifests[0][k] for k in (
        'git_head','model','profiles','skill_manifest','original_reading_config','timeout',
        'max_tokens','thinking','json_mode','repeats','comparison_limitation')})
    skill_path = REPO / 'cfm_id_llm' / manifests[0]['skill_manifest']['resource']
    skill_text = skill_path.read_text(encoding='utf-8')
    if digest(skill_text) != manifests[0]['skill_manifest']['sha256']:
        integrity.append('current Skill text does not match recorded Skill hash')
    else:
        (output / 'Skill_snapshot.md').write_text(skill_text, encoding='utf-8')
    # Persist any Skill issue found after the initial summary write.
    write(output / 'summary.json', result)
    with (output / 'failures.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['split','case_id','profile','repeat','reason','state'])
        writer.writeheader()
        writer.writerows(errors)
    table = '\n'.join(f'| {g["split"]} | {g["profile"]} | {g["responses"]}/{g["attempted"]} | '
        f'{g["parsed"]}/{g["attempted"]} ({g["parsed"]/g["attempted"]:.2%}) | '
        f'{g["prompt_tokens"]:,} | {g["completion_tokens"]:,} |' for g in groups)
    total = sum(g['prompt_tokens']+g['completion_tokens'] for g in groups)
    repeat_text = '\n'.join(f'- {g["split"]}/{g["profile"]}：'+ '；'.join(
        f'第{r["repeat"]}轮 {r["parsed"]}/{r["attempted"]}' for r in g['repeats']) for g in groups)
    reasons = Counter(e['reason'] for e in errors)
    report = f'''# 任务6实验收尾报告

本报告仅重算已有记录，新增模型调用为0。已完成12个独立情境（10网络、2DAG）、24份材料、两方案各两轮的96次A0对照，以及1次单独的N01事实读取记录。当前可交付实验材料、客观统计、错误台账和配置建议；独立语义审读和全链路验收仍待完成，不能宣称任务书全部验收通过。

## 1. 实验设置与证据

开发集N01–N08：8情境、16材料、64次A0；留出集N09–N10及D11–D12：4情境、8材料、32次A0。每个情境包含完整及缺项/矛盾版，重复运行不算新情境。材料自拟，参考答案仍为作者草稿。

模型为`{result['model']}`，代码基线为`{result['git_head']}`。JSON模式、thinking disabled、max_tokens 16384、timeout 300秒。基线合同为target-first-operands-1，候选为实际注入Skill的target-first-skill-1。两者同时改变Prompt和Schema/解析合同，结果只能比较方案整体，不能解释为Skill单因素因果效应。完整参数见experiment_config.json。

## 2. 请求和格式（分母含所有尝试）

| 集合 | 方案 | 收到回答/尝试 | 合同解析通过/尝试 | 输入token | 输出token |
|---|---|---:|---:|---:|---:|
{table}

开发集候选格式通过率高3.125个百分点，留出集高12.5个百分点。格式通过只代表进入后续复核；不能代替语义正确、缺项发现或因果识别正确。

“收到回答”依据runs.json的记录标记；部分记录虽标记raw_response_saved=true，实际文件缺失，须与完整性问题一起阅读，不能宣称全部原始回答可重放。

两轮格式结果：

{repeat_text}

这只是同一批题的两次波动观察，样本小且情境内相关，不作显著性或泛化优势声明。

## 3. 语义、引用与缺项

已有review_assisted.csv和Task6_holdout32_pre_review.csv中的审读者标签均为AI辅助预审。历史scoring_report.json的human_*字段并不证明真实独立人工认证，因此本报告不采用其语义准确率。正式语义、引用、缺项及追问准确率均记为待独立审读。参考Gold也尚未独立认证。

审读须逐项核对目标、比较两端和方向、评价名单/权重、时点背景、A4总体信息、A5假设及引文蕴含；JSON或合同拒绝不能计作正确发现缺项。AI预审作为待核对线索保留，不能用署名字段代替真实审读。

## 4. 错误归因与最终执行

共有{len(errors)}条A0合同/引用校验未通过：{dict(reasons)}。逐条ID、方案、轮次和拒绝原因见failures.csv；这些是校验器给出的机制分类，尚未逐条证实为纯Prompt错误或纯解析器错误。它们应先用已保存回答排查字段与解析合同矛盾，再决定提示改进，不应删除失败后重算分母。

N01既有plan结果为`{chain['state']}` / `{chain['reason_code']}`，backend_called={chain['backend_called']}，无数学证书。已有审核文件正文明确写为模型辅助预审，不能视为独立批准；有人工修订候选，首答、修订及重读须分开计数。该例记录了事实来源审核阻断，不能称为首答全链路成功，也不能据此声称错误认证率为0。全链路正确率和错误认证率尚未测量。

## 5. 调用成本

本次正式对照A0共96次，输入输出合计{total:,} token；另有N01事实读取1次、{chain_diag['usage']['total_tokens']:,} token，合计97次、{total+chain_diag['usage']['total_tokens']:,} token。这不是整个outputs目录的历史总开销；探测、旧实验、重试或其他调用不混入本次对照。各方案输入/输出分别见表。未取得实际结算单价，不推算人民币费用。

## 6. 配置建议

保留项目当前默认配置。候选呈现更高的格式通过率，但缺少独立语义和完整执行证据，尚不足以证明整体业务理解更好；也不能单独归因于Skill。先离线核对11条失败及高风险字段，不修改数学Core或科学批准规则。若以后做净Skill消融，需统一Schema/解析器、冻结Prompt并使用新留出题。

## 7. 冻结、复现与交付边界

本次核对材料哈希、私有/汇总结果一致性、实际system/user文本哈希、请求绑定、开发/留出分离及两集合配置一致性。完整性问题数：{len(integrity)}，明细见summary.json。哈希只能证明当前记录相互一致，不能证明历史上未见过题；已有留出预审后，这批题不得再次声称为全新未见题。未发现正式独立审读签审记录，不替任何研究者签名。

仓库根目录离线复现（输出目录须不存在）：

```powershell
python -m unittest discover -s evaluation/task6/tests -v
python -m evaluation.task6.scripts.closeout --output outputs/task6_closeout_recheck
```

运行closeout仅使用Python标准库，读取已有outputs，绝不创建API请求。公开交付包含evaluation/task6下材料、参考、脚本、测试及本次汇总；原始请求/回答和审核原件保留在outputs受限目录，证据索引见evidence_hashes.json。脚本复现需在本机保留两组原始输出及N01目录；公开汇总包本身不含原始模型回答，无法独立复算模型生成。

尚需本人完成的验收项：由另一位真实研究者审定24份参考及96份A0复核；完成缺项追问和首答最终执行的审计台账。可复用现有事实候选做审核/阻断记录，无需为本次报告重跑API；若要补齐其余题的事实读取全链路，现有A0记录不能替代新的事实证据。当前交付应标注“实验与收尾报告完成，独立审读及全链路指标待验收”。
'''
    (output / '任务6收尾报告.md').write_text(report, encoding='utf-8')
    print(json.dumps({'output':str(output), 'A0_attempts':96,
                      'integrity_issues':integrity, 'new_api_calls':0}, ensure_ascii=False))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    closeout(parser.parse_args().output)
