// No browser, server or API: execute the real page script with a minimal DOM.
// Run: node --test tests_integration/test_review_ui.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const app = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
const clone = x => JSON.parse(JSON.stringify(x));

function harness(view) {
  const elements = new Map(), requests = [];
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      hidden:false, disabled:false, open:false, checked:false, value:'', textContent:'', innerHTML:'',
      querySelectorAll:() => [], focus() {}, append() {},
    });
    return elements.get(selector);
  }
  function readRows(html) {
    for (const match of html.matchAll(/<article class="review-row" id="([^"]+)">([\s\S]*?)<\/article>/g)) {
      const row = element('#'+match[1]), refs = [];
      for (const input of match[2].matchAll(/<input type="checkbox" data-ref="([^"]+)"\s*(checked)?/g))
        refs.push({dataset:{ref:input[1]}, checked:!!input[2]});
      row.reason = {value:''}; row.rejected = match[2].includes('value="REJECTED" selected');
      row.querySelector = s => s === '.reason' ? row.reason : null;
      row.querySelectorAll = s => s === '[data-ref]:checked' ? refs.filter(x=>x.checked) : [];
    }
  }
  let fieldsHTML = '';
  Object.defineProperty(element('#review-fields'), 'innerHTML', {
    get:()=>fieldsHTML, set:html=>{ fieldsHTML=html; readRows(html); }
  });
  const document = {
    querySelector:s=>s.includes('option[value="REJECTED"]')
      ? [...elements.values()].find(x=>x.rejected)||null : element(s),
    querySelectorAll:()=>[], createElement:()=>({}),
  };
  const context = vm.createContext({document, structuredClone, console, Date,
    setTimeout:()=>1, clearTimeout:()=>{},
    fetch:async(url,options)=>{
      if(options.method==='POST') { requests.push(JSON.parse(options.body)); return {ok:true,json:async()=>({})}; }
      return {ok:true,json:async()=>({...clone(view),busy:true})};
    },
  });
  vm.runInContext(app.replace(/init\(\);\s*$/, ''), context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../input-files.js'),'utf8'),context);
  const terms=JSON.parse(fs.readFileSync(path.join(__dirname,'../condition_terms.json'),'utf8'));
  context.catalog=Object.fromEntries(Object.entries(terms).map(([key,[term,label,category]])=>[key,{key,term,label,category,text:label}]));
  vm.runInContext('conditionTerms=catalog;',context);
  context.fixture = clone(view);
  vm.runInContext('current=fixture; runId=fixture.id; renderRun(current);', context);
  return {element,requests,context,
    summary:()=>clone(vm.runInContext('reviewSummary(current)',context)),
    confirm:()=>element('#confirm-summary').onclick(),
    poll:()=>vm.runInContext('poll()',context),
  };
}

function fixture(kind='query') {
  const dimension={field_role:'PENDING',value_state:'PENDING',source_coverage:'PENDING'};
  const candidate={version:'network-randomized-effect-reading-1',
    study:{outcome:'本周每小时净收入'},
    target:{first:{own:1,exposure:0},second:{own:0,exposure:0},population:['甲','乙'],aggregation:'EQUAL_MEAN'},
    exposure:{kind:'STRICT_MAJORITY_TIES_LOW'},
    assignment:{kind:'INDEPENDENT_BERNOULLI',probabilities:{'甲':'1/2','乙':'1/2'}},
    scientific_statements:Object.fromEntries(['consistency','assignment_outcome_independence','finite_conditional_means'].map(k=>[k,{status:'PROPOSED'}])),
    information:[{availability:'SYMBOLIC_POPULATION_OPERATOR'}], additional_restrictions:[],unresolved:[]};
  return {id:'a'.repeat(32),query_id:'q1',review_kind:kind,stage:'REVIEW_REQUIRED',busy:false,events:[],downloads:[],
    queries:[{query_id:'q1',business_goal:{value:'自己用助手比不用时，每小时净收入增加多少？'},
      semantics:{target_population:{value:'甲乙两人'},aggregation:{value:'等权平均'}}}],
    attachment_report:{factual_data:{nodes:2,observed:1,features:20}},
    review_templates:{[kind]:{binding_sha256:'fixture-binding',authority:'SYNTHETIC_TEST',
      decisions:{check:['query','source'].includes(kind)?clone(dimension):'PENDING'}}},
    review_sheets:{[kind]:{binding_sha256:'fixture-binding',fields:{
      'common.outcome':{candidate:{value:'本周每小时净收入'}},
      ...(kind==='source'?{'':{candidate}}:{})},source_catalog:{s1:{text:'冻结的测试材料'}}}},
    plan:kind==='query'?null:{reading_candidate:candidate,methods:[{method:'R1A_COMPOSITION'}]},
  };
}

function compact(h, available) {
  assert.equal((h.element('#compact-review').innerHTML.match(/<article>/g)||[]).length,3);
  assert.equal(h.element('#compact-review').hidden,false);
  assert.equal(h.element('#review-details').open,false);
  assert.equal(h.element('#confirm-summary').hidden,false);
  assert.equal(h.element('#confirm-summary').disabled,!available);
}

if (require.main === module) {
  test('rapid query selection sends only one action',async()=>{
    const view=fixture();view.stage='SELECT_QUERY';const h=harness(view);
    const click=()=>h.element('#query-select').onclick({target:{dataset:{query:'q1'}}});
    await Promise.all([click(),click()]);
    assert.equal(h.requests.filter(x=>x.action==='select').length,1);
  });
  test('A0 stopping before audit never claims completed model review',()=>{
    const view=fixture();view.review_kind=null;view.automatic_review=true;
    view.result={state:'READING_RECHECK_REQUIRED',reason_code:'COMPACT_SCHEMA_REJECTED'};
    const html=harness(view).element('#result').innerHTML;
    assert.doesNotMatch(html,/业务解释经过模型自动复核/);
    assert.match(html,/尚未得到通过证书重放/);
  });
  test('fixed-policy R1b uses three cards and one explicit confirmation; missing science still blocks',async()=>{
    const view=fixture('science');view.automatic_review=true;
    const f=view.plan.reading_candidate;f.version='network-source-selections-1';
    f.target={kind:'FIXED_POLICY_MEAN',assignment:{'甲店':1,'乙店':0},population:['甲店','乙店'],aggregation:'EQUAL_MEAN'};
    f.information[0].operator='ALL_OUTCOMES_TOGETHER_WITH_FULL_ASSIGNMENT';
    view.plan.methods=[{method:'R1B_FULL_ASSIGNMENT'}];
    const h=harness(view);compact(h,true);
    assert.match(h.element('#compact-review').innerHTML,/甲店接受处理；乙店不接受处理/);
    assert.match(h.element('#compact-review').innerHTML,/联合总体分布/);
    assert.equal(h.requests.length,0);await h.confirm();assert.equal(h.requests.length,1);
    for(const status of ['NOT_STATED','UNDECIDED','NOT_ADOPTED','CONFLICTING']){
      const missing=clone(view);missing.plan.reading_candidate.scientific_statements.consistency.status=status;
      compact(harness(missing),false);
    }
    view.plan.methods[0].method='R2_MEAN_SIGNATURE';compact(harness(view),false);
  });
  test('explicitly adopted conditions can be confirmed and remain visible; unknowns cannot',async()=>{
    const view=fixture('science');view.automatic_review=true;
    for(const item of Object.values(view.plan.reading_candidate.scientific_statements))item.status='ADOPTED';
    const h=harness(view);compact(h,true);
    assert.match(h.element('#compact-review').innerHTML,/原文明确采用/);
    assert.match(h.element('#compact-review').innerHTML,/实际结果对应实际完整安排/);
    assert.equal(h.requests.length,0);await h.confirm();assert.equal(h.requests.length,1);
    for(const status of ['UNDECIDED','NOT_ADOPTED','NOT_STATED','CONFLICTING']){
      const missing=clone(view);missing.plan.reading_candidate.scientific_statements.consistency.status=status;
      compact(harness(missing),false);
    }
  });
  test('ID result explains both arms and conditions without rendering an injected estimate',()=>{
    const view=fixture('source');view.review_kind=null;view.automatic_review=true;
    view.result={state:'POINT',independent_replay:true,mathematical_claim:{kind:'POINT',target:{
      kind:'DIRECT_EFFECT',first:[1,0],second:[0,0],exposure:'STRICT_MAJORITY_TIES_LOW',
      evaluation_population:['甲','乙'],unit_weights:['1/2','1/2'],outcome:'每小时净收入',
      treatment:'启用助手为1，未启用为0',remaining_assignment:'ORIGINAL_DESIGN_CONDITIONAL'}},
      certificate:{results:[{assumptions_used:['consistency','full_vector_randomization']}]},
      assumption_choices_review:{retained:[{condition:'MEAN_EXPOSURE_SUFFICIENCY',status:'UNDECIDED',required:false}]}};
    view.estimate={state:'ESTIMATED',estimate:{estimate:2.5,estimand:{outcome:'元/小时'}}};
    const h=harness(view),html=h.element('#result').innerHTML;
    assert.match(html,/自己用助手/);assert.match(html,/本人接受处理/);assert.match(html,/减去：本人不接受处理/);
    assert.match(html,/至多一半/);assert.match(html,/识别公式/);assert.match(html,/<math display="block">/);
    assert.match(html,/本次结论依赖的条件/);assert.match(html,/原随机设计在对应条件下平均/);
    assert.doesNotMatch(html,/2\.5000/);assert.doesNotMatch(html,/模型估计/);assert.doesNotMatch(html,/<mfrac><mn>1<\/mn>/);
    assert.match(html,/尚未决定是否采用同伴分组的均值充分性/);assert.match(html,/所用方法不需要/);
    assert.equal(h.element('#clarification').hidden,true);
    assert.equal(h.element('#review').hidden,true);
  });
  test('clarification displays the actual cited passage without showing internal field paths',()=>{
    const view=fixture('source');view.automatic_review=true;
    view.user_question={items:[{question:'检查additional_restrictions的before与after',
      display_question:'这段话只是说明资料范围，还是另外增加计算条件？',source_texts:['只提供各人的总体分布。']}]};
    const h=harness(view),html=h.element('#clarification-questions').innerHTML;
    assert.match(html,/这段话只是说明/);assert.match(html,/只提供各人的总体分布/);
    assert.doesNotMatch(html,/additional_restrictions|before|after/);
  });
  test('automatic workflow hides routine review pages and technical stepper',()=>{
    for(const kind of ['query','source']){
      const view=fixture(kind);view.automatic_review=true;
      const h=harness(view);
      assert.equal(h.element('#review').hidden,true);
      assert.equal(h.element('#steps').hidden,true);
      assert.equal(h.element('#clarification').hidden,true);
    }
  });
  test('only a concrete clarification is shown; source form stays hidden',()=>{
    const view=fixture('source');view.automatic_review=true;
    view.user_question={message:'原材料尚不清楚',items:[{question:'只评价甲乙两人，还是评价全体？'}]};
    const h=harness(view);
    assert.equal(h.element('#review').hidden,true);
    assert.equal(h.element('#clarification').hidden,false);
    assert.match(h.element('#clarification-questions').innerHTML,/只评价甲乙/);
  });
  test('pending scientific adoption is a visible question, never a background approval',()=>{
    const view=fixture('science');view.automatic_review=true;
    const h=harness(view);assert.equal(h.element('#review').hidden,false);assert.equal(h.requests.length,0);
    assert.match(h.element('#review-title').textContent,/可以吗/);
  });
  test('extra notes are shown with their actual content, not only a generic error',()=>{
    const view=fixture('source');view.plan.reading_candidate.additional_restrictions=[{text:'仅说明资料范围',source_ids:[]}];
    const h=harness(view);assert.match(h.element('#review-issues').innerHTML,/仅说明资料范围/);
    assert.match(h.element('#review-issues').innerHTML,/这不等于你的材料缺少条件/);
    assert.equal(h.element('#request-recheck').disabled,true); // old server: no invented action
  });
  for (const kind of ['query','source','science','data']) test(`legacy ${kind}: three cards, one action, unchanged bound records`,async()=>{
    const view=fixture(kind), before=clone(view), h=harness(view);
    compact(h,true); assert.equal(h.requests.length,0);
    assert.equal(h.summary().is_approval,false);
    assert.ok(h.element('#compact-review').innerHTML.includes('每小时净收入'));
    await h.confirm();
    assert.equal(h.requests.length,1);
    const payload=h.requests[0].payload;
    assert.equal(payload.kind,kind);
    assert.equal(payload.records[kind].binding_sha256,view.review_templates[kind].binding_sha256);
    assert.equal(payload.records[kind].authority,'SYNTHETIC_TEST');
    assert.equal(typeof payload.records[kind].decisions.check==='object'
      ?payload.records[kind].decisions.check.value_state:payload.records[kind].decisions.check,'ACCEPTED');
    assert.deepEqual(view,before);
  });
  test('null, partial and malformed summaries use the same closed default',()=>{
    for(const summary of [null,{}, {cards:[]}, {cards:[null,null,null]}, {cards:'invalid'}]){
      const view=fixture();view.review_summary=summary;compact(harness(view),true);
    }
  });
  test('valid backend summary is kept; explicit refusal is never replaced',async()=>{
    const view=fixture();view.review_summary=harness(view).summary();
    view.review_summary.cards[0].lines=['来自后台的当前目标'];
    const h=harness(view);compact(h,true);assert.ok(h.element('#compact-review').innerHTML.includes('来自后台'));
    view.review_summary.compact_confirmation_available=false;
    const stopped=harness(view);compact(stopped,false);await stopped.confirm();assert.equal(stopped.requests.length,0);
  });
  test('missing records, sources, stale binding and complex records stay collapsed and block',async()=>{
    const variants=[r=>{r.review_templates={};},r=>{r.review_sheets.query.source_catalog={};},
      r=>{r.review_templates.query.binding_sha256='stale';},
      r=>{r.review_templates.query.material_decisions={s1:'PENDING'};},r=>{r.review_kind='notes';}];
    for(const change of variants){const view=fixture();change(view);const h=harness(view);compact(h,false);await h.confirm();assert.equal(h.requests.length,0);}
  });
  test('unknown science may be read as unknown, but cannot be approved as adopted',async()=>{
    for(const status of ['NOT_STATED','UNDECIDED','REJECTED']){
      const source=fixture('source');source.plan.reading_candidate.scientific_statements.consistency.status=status;
      const reading=harness(source);compact(reading,true);
      const science=fixture('science');science.plan.reading_candidate.scientific_statements.consistency.status=status;
      const approval=harness(science);compact(approval,false);await approval.confirm();assert.equal(approval.requests.length,0);
      assert.ok(approval.element('#compact-review').innerHTML.includes({NOT_STATED:'原文未声明',UNDECIDED:'尚未决定',REJECTED:'不采用'}[status]));
    }
  });
  test('two-policy confirmation displays signed endpoints and blocks scope mismatch',async()=>{
    const view=fixture('science'),f=view.plan.reading_candidate;
    f.version='network-policy-contrast-reading-1';
    f.target={kind:'FIXED_POLICY_MEAN_DIFFERENCE',operation:'FIRST_MINUS_SECOND',
      first:{assignment:{a:1,b:1},population:['a','b'],aggregation:'EQUAL_MEAN'},
      second:{assignment:{a:0,b:0},population:['a','b'],aggregation:'EQUAL_MEAN'},shared_outcome_and_context:{value:true}};
    view.plan.methods=[{method:'R1B_ENDPOINT_DIFFERENCE'}];
    const h=harness(view);compact(h,true);assert.match(h.element('#compact-review').innerHTML,/减去第二方案/);
    assert.match(h.element('#compact-review').innerHTML,/2 个评价对象/);
    await h.confirm();assert.equal(h.requests.length,1);
    f.target.second.population=['a'];const blocked=harness(view);compact(blocked,false);await blocked.confirm();assert.equal(blocked.requests.length,0);
  });
  test('two-stage exclusion is never silently included in one-click approval',async()=>{
    const view=fixture('science'),f=view.plan.reading_candidate;
    f.assignment={kind:'TWO_STAGE_QUOTA_MIXTURE'};
    compact(harness(view),false);
    f.first_stage_exclusion={status:'PROPOSED'};const h=harness(view);compact(h,true);
    assert.match(h.element('#compact-review').innerHTML,/名额方案本身不再直接影响结果/);
    f.first_stage_exclusion.status='NOT_ADOPTED';compact(harness(view),false);
  });
  test('replayed design-specific anchor conditions are shown with the final formula',()=>{
    const h=harness(fixture());
    h.context.evidence={independent_replay:true,certificate:{assumptions_used:['consistency']},answers:[{
      independent_replay:true,native_evidence:{result:{source_batch:{anchor:{result:{assumptions_used:['first_stage_profile_no_direct_outcome_effect']}}}}}}]};
    assert.equal(vm.runInContext('certifiedAssumptions(evidence).includes("first_stage_profile_no_direct_outcome_effect")',h.context),true);
    h.context.evidence.independent_replay=false;
    assert.equal(vm.runInContext('certifiedAssumptions(evidence).includes("first_stage_profile_no_direct_outcome_effect")',h.context),false);
  });
  test('extra restrictions, unresolved facts and unsupported routes cannot be bulk approved',async()=>{
    for(const change of [r=>r.plan.reading_candidate.additional_restrictions.push('额外等式'),
      r=>r.plan.reading_candidate.unresolved.push('总体信息缺失'),r=>r.plan.methods[0].method='OTHER',
      r=>r.plan.rejected_fields=['/target']]){
      const view=fixture('science');change(view);const h=harness(view);compact(h,false);await h.confirm();assert.equal(h.requests.length,0);
    }
  });
  test('stored or user-selected rejection is never overwritten',async()=>{
    const view=fixture();view.review_templates.query.decisions.check.value_state='REJECTED';
    const stored=harness(view);compact(stored,false);await stored.confirm();assert.equal(stored.requests.length,0);
    const edited=harness(fixture());edited.element('#r0').rejected=true;await edited.confirm();
    assert.equal(edited.requests.length,0);assert.equal(edited.element('#review-details').open,false);
    assert.match(edited.element('#review-message').textContent,/拒绝/);
  });
  test('refreshing an unchanged legacy binding still allows exactly one submission',async()=>{
    const h=harness(fixture());
    vm.runInContext('current=structuredClone(fixture); renderRun(current);',h.context);
    compact(h,true);
    await Promise.all([h.confirm(),h.confirm()]);assert.equal(h.requests.length,1);
  });
  test('new details are opt-in; polling does not close details the user opened',()=>{
    const h=harness(fixture());h.element('#review-details').open=true;
    vm.runInContext('renderRun(current)',h.context);assert.equal(h.element('#review-details').open,true);
  });
  test('summary escapes material text; the detailed submit button is inside the closed disclosure',()=>{
    const view=fixture();view.queries[0].business_goal.value='<img src=x onerror=alert(1)>';
    const h=harness(view);assert.ok(!h.element('#compact-review').innerHTML.includes('<img'));
    const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
    assert.match(html,/<details id="review-details" class="optional">/);
    assert.match(html,/<details id="review-details"[\s\S]*id="review-fields"[\s\S]*id="submit-review"[\s\S]*<\/details>/);
  });
}
module.exports={harness};

function registeredFixture(){
 const v=fixture('science');v.plan={state:'REVIEW_REQUIRED',plan_sha256:'p'.repeat(64),methods:[{method:'DAG_CLASSICAL_FRONTDOOR'}]};
 const sheet={version:'dag-frontdoor-1',problem_sha256:'d'.repeat(64),decisions:{complete_causal_graph_and_latents:'PENDING'}};
 v.review_sheets={native:clone(sheet)};v.review_templates={native:{...clone(sheet),authority:'SYNTHETIC_TEST',reviewer:'',evidence:''}};
 v.review_summary={contract:'registered-web-review-1',plan_sha256:v.plan.plan_sha256,methods:['DAG_CLASSICAL_FRONTDOOR'],
  review_bindings:{native:{identity:{version:sheet.version,problem_sha256:sheet.problem_sha256},decisions:Object.keys(sheet.decisions)}},
  cards:[{title:'目标',lines:['培训干预分布']},{title:'科学条件',lines:['完整图及潜变量；理想干预']},{title:'总体信息',lines:['已知观测联合总体分布及正支持']}],
  compact_confirmation_available:true,needs_individual_attention:[],confirmation_label:'确认采用上述条件并识别',is_approval:false};
 return v;
}
test('registered DAG confirmation preserves native identity without inventing a common hash',async()=>{
 const h=harness(registeredFixture());assert.equal(h.summary().compact_confirmation_available,true);
 await h.confirm();assert.equal(h.requests.length,1);
 const r=h.requests[0].payload.records.native;assert.equal(r.problem_sha256,'d'.repeat(64));assert.equal('binding_sha256' in r,false);
 assert.equal(r.decisions.complete_causal_graph_and_latents,'ACCEPTED');
});
test('registered summary cannot conceal changed plan, method, refused key or omitted worksheet',()=>{
 for(const mutate of [v=>v.review_summary.plan_sha256='stale',v=>v.review_summary.methods=['OTHER'],
  v=>v.review_templates.native.decisions.complete_causal_graph_and_latents='REJECTED',
  v=>delete v.review_summary.review_bindings.native,v=>v.review_templates.native.problem_sha256='changed']){
  const v=registeredFixture();mutate(v);assert.equal(harness(v).summary().compact_confirmation_available,false);
 }
});
test('registered symbolic R2 and R3 render signature condition, not a zero-support full arrangement',()=>{
 const h=harness(registeredFixture());
 for(const route of ['R2','R3_MEAN_SIGNATURE']){
  h.context.resultFixture={certificate:{route},mathematical_claim:{kind:'POINT',target:{assignment:[1,1],kind:'FIXED_FULL_ASSIGNMENT_POLICY_MEAN'}}};
  const html=vm.runInContext('formulaHTML(resultFixture)',h.context);
  assert.match(html,/gᵢ\(a\)/);assert.doesNotMatch(html,/T = \(1, 1\)/);
 }
});
test('DAG formula comes from the certified functional and partial fractions render as fractions',()=>{
 const h=harness(registeredFixture());h.context.resultFixture={mathematical_claim:{kind:'POINT',functional:{operation:'COVARIATE_ADJUSTMENT',outcome:'Y',treatment:'T',sum_over:['Z'],conditional:{outcomes:['Y'],given:['T','Z']},marginal:{variables:['Z']}}}};
 const shown=vm.runInContext('formulaHTML(resultFixture)',h.context);
 assert.match(shown,/do\(x\)/);assert.match(shown,/<dt>X<\/dt><dd>T /);
 assert.doesNotMatch(shown.match(/<math[\s\S]*?<\/math>/)[0],/do\(T\)/);
 h.context.resultFixture={mathematical_claim:{representation:'EXACT_IDENTIFIED_INTERVAL',target:{kind:'FIXED_FULL_ASSIGNMENT_POLICY_CONTRAST'},interval:['1/5','1']}};
 const html=vm.runInContext('formulaHTML(resultFixture)',h.context);assert.match(html,/<mfrac>/);assert.match(html,/Δ/);
});

test('symbol aliases are derived from variable roles and preserve multi-variable adjustment',()=>{
 const h=harness(registeredFixture());
 const f={operation:'BACKDOOR_ADJUSTMENT',outcome:'康复',treatment:'治疗',sum_over:['年龄','病情'],conditional:{outcomes:['康复'],given:['治疗','年龄','病情']},marginal:{variables:['年龄','病情']}};
 h.context.f=f;
 const math=vm.runInContext('dagFormula(f)',h.context),legend=vm.runInContext('symbolLegend(f)',h.context);
 assert.match(math,/z1, z2/);assert.doesNotMatch(math,/康复|治疗|年龄|病情/);
 for(const word of ['康复','治疗','年龄','病情'])assert.ok(legend.includes(word));
 h.context.f={...f,treatment:'投放',outcome:'购买',sum_over:['地区','价格'],conditional:{outcomes:['购买'],given:['投放','地区','价格']},marginal:{variables:['地区','价格']}};
 assert.equal(vm.runInContext('dagFormula(f)',h.context),math);
 assert.doesNotMatch(vm.runInContext('symbolLegend(f)',h.context),/康复|治疗/);
 h.context.f.conditional.given.push('未声明变量');assert.throws(()=>vm.runInContext('dagFormula(f)',h.context),/Unbound/);
});

test('result conditions use executed evidence and never example-authored defaults',()=>{
 const h=harness(fixture());h.context.r={state:'POINT',independent_replay:true,certificate:{assumptions_used:['consistency','full_vector_randomization']}};
 const html=vm.runInContext('resultHTML(r,null,["预写答案：无混杂、无干扰"])',h.context);
 assert.match(html,/Consistency/);assert.match(html,/Randomization/);assert.doesNotMatch(html,/预写答案|No interference|Conditional exchangeability/);
 h.context.r.certificate={source_batch_sha256:'x'};h.context.r.condition_record={origin:'EXECUTED_CERTIFICATES',source_batch_sha256:'different',keys:['consistency']};
 assert.equal(vm.runInContext('resultConditions(r).length',h.context),0);
 h.context.r.condition_record.source_batch_sha256='x';assert.equal(vm.runInContext('resultConditions(r)[0].term',h.context),'Consistency');
});

test('compact science cards separate decisions from context and retain every complete statement',()=>{
 const v=registeredFixture();
 v.review_summary.condition_items=v.review_summary.cards[1].lines.map(text=>({text,term:'Consistency',label:'一致性',category:'science'}));
 const h=harness(v),html=h.element('#compact-review').innerHTML;
 assert.match(html,/① 研究目标/);assert.match(html,/② 研究假设/);assert.match(html,/③ 可用信息/);
 assert.match(html,/需你确认采用/);assert.match(html,/<details id="confirmation-scope" class="optional">/);
 for(const c of v.review_summary.cards)for(const text of c.lines)assert.ok(html.includes(text));
 assert.deepEqual(h.summary().review_bindings,v.review_summary.review_bindings);
});

function informationFixture(){
 const v=fixture('information');const sheet={version:'network-contrast-information-evidence-review-1',binding_sha256:'f'.repeat(64),
  source_catalog:{a:{doc_id:'总体均值表',text:'甲店本人与同伴不使用时总体均值为1/2。'},b:{doc_id:'研究说明',text:'甲指名册第一店；本周。'},c:{doc_id:'总体均值表',text:'乙店总体均值为1/3。'}},entry_source_ids:{0:['a','b'],1:['c','b']}};
 v.review_sheets={information:sheet};v.review_templates={information:{version:sheet.version,binding_sha256:sheet.binding_sha256,authority:'SYNTHETIC_TEST',disposition:'PENDING',table_source_ids:[],supporting_source_ids:[],reviewer:'',evidence:''}};
 return v;
}
test('information question requires explicit document choice and preserves exact source partition',async()=>{
 const v=informationFixture(),h=harness(v);assert.equal(h.element('#confirm-summary').disabled,true);
 assert.match(h.element('#compact-review').innerHTML,/总体均值表/);await h.confirm();assert.equal(h.requests.length,0);
 vm.runInContext('informationChoices[current.id+":"+current.review_sheets.information.binding_sha256]="总体均值表"',h.context);
 await h.confirm();const r=h.requests[0].payload.records.information;
 assert.deepEqual(r.table_source_ids,['a','c']);assert.deepEqual(r.supporting_source_ids,['b']);assert.equal(r.disposition,'ACCEPTED');
 assert.equal(v.review_templates.information.disposition,'PENDING');
});
test('information choice cannot skip an entry, reuse stale review, or overwrite refusal',()=>{
 for(const mutate of [v=>v.review_sheets.information.entry_source_ids[1]=['b'],v=>v.review_templates.information.binding_sha256='0'.repeat(64),v=>v.review_templates.information.disposition='REJECTED']){
  const v=informationFixture();mutate(v);const h=harness(v);
  assert.throws(()=>vm.runInContext('informationRecords(current,{[current.id+":"+current.review_sheets.information.binding_sha256]:"总体均值表"})',h.context));
 }
});
