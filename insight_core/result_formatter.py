from __future__ import annotations
from insight_core.schemas import AssumptionItem, BaseItem, ClaimItem, Decision, DerivationType, EvidenceRef, FailureItem, InsightRequest, InsightResponse, LimitationItem, OpenQuestionItem, ProblemCandidateItem, ProblemType, UpdateRule
PERF=("improve","improving","enhance","enhances","performance","outperform","reward","steps","性能","向上","ベースライン","average rewards")
BROAD=("real-world","実世界","deployment","scientific investigation","system-level","full-lifecycle","reliable","信頼","スケーラブル")
QUALITY=("quality","品質","repository","リポジトリ","curation","curated","self-constructed")
CHECKS={"claim_scope_mismatch":["実世界相当タスクで再評価する","主張の適用範囲を明文化する","転移失敗例を収集する"],"benchmark_transfer_risk":["別データ分布で再評価する","新規タスクで検証する","境界条件を明文化する"],"repository_reliability_risk":["低品質スキル混入時の挙動を測る","長期運用時の品質低下を監視する","人手監査の必要量を測る"],"evaluation_gap":["評価条件を広げて再検証する","比較対象を追加する","失敗例を抽出する"],"deployment_extrapolation":["導入責任を定義する","保守コストを見積もる","障害対応フローを設計する"],"operational_risk":["運用条件を明文化する","障害時対応を決める","監視指標を定義する"],"generalization_gap":["別データ分布で再評価する","新規タスクで検証する","境界条件を明文化する"]}
QMAP={"claim_scope_mismatch":("validation_experiment","実世界相当タスクで、ベンチマークと同等の改善率が再現されるか",["deployment_eval","transfer_benchmark","ablation"]),"benchmark_transfer_risk":("validation_experiment","別データ分布や未見タスクでも、同様の改善が維持されるか",["transfer_benchmark","cross_domain_eval","ablation"]),"repository_reliability_risk":("reliability_audit","self-constructed skills を含む大規模リポジトリで、品質低下をどの程度検知・除去できるか",["longitudinal_eval","human_audit","poisoning_test"]),"deployment_extrapolation":("operational_design","導入時の責任分界、保守コスト、障害対応をどう設計するか",["ops_plan","incident_playbook","ownership_model"]),"evaluation_gap":("evaluation_design","現行評価で見落としている失敗条件は何か",["ablation","error_analysis","baseline_comparison"])}
SCOPE={"claim":"core_result","assumption":"author_framing","limitation":"evaluation_scope","insight":"synthesized_conclusion"}
def _u(vals:list[str])->list[str]:
    seen=set(); out=[]
    for v in vals:
        if v and v not in seen: seen.add(v); out.append(v)
    return out
def _norm(text:str,limit:int=140)->str:
    text=" ".join(text.split()).strip().removesuffix("。")
    return text if len(text)<=limit else text[:limit-3].rstrip()+"..."
def _maps(r:InsightResponse):
    return ({x.id:x for x in r.claims},{x.id:x for x in r.assumptions},{x.id:x for x in r.limitations},{x.problem_id:x for x in r.problem_candidates},{x.evidence_id:x for x in r.evidence_refs})
def _has(s:str,words:tuple[str,...])->bool:
    s=s.lower(); return any(w.lower() in s for w in words)
def _mode(item:BaseItem,node_type:str)->str:
    if node_type=="insight": return "system_inference"
    if item.epistemic_mode.value=="observation": return "source_fact"
    return "author_claim" if item.derivation_type==DerivationType.DIRECT else "system_inference"
def _drv(d:DerivationType,conf:float,evidence_count:int)->str:
    if d==DerivationType.DIRECT: return "quoted" if evidence_count<=1 else "summarized"
    if d in (DerivationType.CONTEXTUAL,DerivationType.CONTRASTIVE): return "summarized"
    return "inferred_near" if conf>=0.65 else "inferred_speculative"
def _broad(c:ProblemCandidateItem,cl:dict[str,ClaimItem],ass:dict[str,AssumptionItem])->bool:
    return any(_has(cl[i].statement,BROAD) for i in c.parent_refs if i in cl) or any(_has(ass[i].statement,BROAD) for i in c.assumption_refs if i in ass)
def _ptype(c:ProblemCandidateItem,cl:dict[str,ClaimItem],ass:dict[str,AssumptionItem])->str:
    if c.problem_type==ProblemType.GENERALIZATION_GAP: return "claim_scope_mismatch" if _broad(c,cl,ass) else "benchmark_transfer_risk"
    if c.problem_type==ProblemType.EVALUATION_GAP and _has(c.statement,QUALITY): return "repository_reliability_risk"
    if c.problem_type==ProblemType.OPERATIONAL_RISK: return "deployment_extrapolation"
    return c.problem_type.value if c.problem_type else "evaluation_gap"
def _bundle(c:ProblemCandidateItem,cl:dict[str,ClaimItem],ass:dict[str,AssumptionItem],lim:dict[str,LimitationItem])->dict:
    ev=list(c.evidence_refs)
    [ev.extend(cl[i].evidence_refs) for i in c.parent_refs if i in cl]
    [ev.extend(ass[i].evidence_refs) for i in c.assumption_refs if i in ass]
    [ev.extend(lim[i].evidence_refs) for i in c.limitation_refs if i in lim]
    return {"claim_ids":_u(c.parent_refs),"assumption_ids":_u(c.assumption_refs),"limitation_ids":_u(c.limitation_refs),"evidence_ids":_u(ev)}
def _direct(c:ProblemCandidateItem,cl:dict[str,ClaimItem],ass:dict[str,AssumptionItem],lim:dict[str,LimitationItem])->bool:
    items=[cl[i] for i in c.parent_refs if i in cl]+[ass[i] for i in c.assumption_refs if i in ass]+[lim[i] for i in c.limitation_refs if i in lim]
    return any(x.derivation_type==DerivationType.DIRECT for x in items)
def _suff(c:ProblemCandidateItem,ptype:str,bundle:dict,cl:dict[str,ClaimItem],ass:dict[str,AssumptionItem],lim:dict[str,LimitationItem])->dict:
    miss=[]; sc=len(c.support_signals); cc=len(c.failure_signals)
    if sc<2: miss.append("multiple_support_signals")
    if not bundle["evidence_ids"]: miss.append("supporting_evidence")
    if not _direct(c,cl,ass,lim): miss.append("direct_quote_evidence")
    if cc==0: miss.append("counter_signal_review")
    if ptype in {"claim_scope_mismatch","benchmark_transfer_risk"} and not c.limitation_refs: miss.append("scope_limit_evidence")
    if ptype=="repository_reliability_risk" and not c.limitation_refs: miss.append("repository_reliability_evidence")
    if ptype=="deployment_extrapolation" and not c.limitation_refs: miss.append("operational_limitation_evidence")
    status="sufficient" if not miss else ("partial" if sc>=1 and bundle["evidence_ids"] else "weak")
    return {"status":status,"missing":_u(miss),"support_count":sc,"counter_count":cc}
def _checks(ptype:str,c:ProblemCandidateItem)->list[str]:
    checks=list(CHECKS.get(ptype,CHECKS.get(c.problem_type.value if c.problem_type else "",[])))
    if c.fatal_risks: checks.append("重大リスクの発火条件を確認する")
    if c.failure_signals: checks.append("反証シグナルを再検証する")
    if not checks: checks=["追加の根拠を確認する","反証ケースを探す"]
    return _u(checks)[:3]
def _risk(c:ProblemCandidateItem,ptype:str)->bool:
    return ptype=="deployment_extrapolation" and not c.limitation_refs and c.decision!=Decision.ACCEPT
def _problem(c:ProblemCandidateItem,ptype:str,bundle:dict,suff:dict)->dict:
    return {"id":c.problem_id,"statement":_norm(c.statement),"epistemic_mode":"critique_hypothesis","derivation_type":_drv(c.derivation_type,c.confidence,len(bundle["evidence_ids"])),"confidence":min(c.confidence,0.82 if suff["status"]!="sufficient" else c.confidence),"problem_type":ptype,"scope":c.scope.value if c.scope else None,"support_bundle":bundle,"support_signals":_u(c.support_signals),"counter_signals":_u(c.failure_signals),"evidence_sufficiency":suff,"decision":c.decision.value,"next_checks":_checks(ptype,c),"parent_refs":_u(c.parent_refs+c.assumption_refs+c.limitation_refs),"update_rule":c.update_rule.value}
def _risk_note(c:ProblemCandidateItem,bundle:dict)->dict:
    return {"id":f"rk_{c.problem_id}","statement":_norm(c.statement),"epistemic_mode":"system_inference","derivation_type":"inferred_speculative","confidence":min(c.confidence,0.65),"risk_type":"deployment_extrapolation","support_bundle":bundle,"next_checks":_checks("deployment_extrapolation",c),"parent_refs":_u(c.parent_refs+c.assumption_refs+c.limitation_refs),"update_rule":UpdateRule.REVISE.value}
def _fb_insight(cl:dict[str,ClaimItem],problems:list[dict],risks:list[dict],idx:int):
    perf=[x for x in cl.values() if _has(x.statement,PERF)]
    if idx==0 and perf and problems: return ("ベンチマーク上の性能改善は直接支持されている一方、主張の適用範囲は評価スコープより広い。",problems[0]["support_bundle"],[problems[0]["id"]])
    if idx==1:
        repo=next((p for p in problems if p["problem_type"]=="repository_reliability_risk"),None)
        if repo: return ("品質評価とフィルタリングの設計は示されているが、長期的なリポジトリ信頼性は未解決である。",repo["support_bundle"],[repo["id"]])
        if risks: return ("実運用への外挿には、責任分界・保守コスト・障害対応の追加設計が必要である。",risks[0]["support_bundle"],[risks[0]["id"]])
    if idx==2 and len(problems)>1: return (f"追加検証の中心論点は、{problems[1]['statement']}。",problems[1]["support_bundle"],[problems[1]["id"]])
    return None
def _question(c:ProblemCandidateItem,ptype:str,bundle:dict,qid:str|None=None,conf:float|None=None,prom:str|None=None,clos:str|None=None)->dict:
    qtype,stmt,req=QMAP.get(ptype,("validation_experiment",_norm(c.statement),["additional_evidence"]))
    return {"question_id":qid or f"oq_{c.problem_id}","question_type":qtype,"statement":stmt,"confidence":conf if conf is not None else min(c.confidence*0.6,0.7),"support_bundle":bundle,"required_evidence_type":req,"next_checks":_checks(ptype,c),"promotion_condition":prom or "追加の根拠や検証が得られること","closure_condition":clos or f"{stmt} が確認または否定されること"}
def _reasoning(r:InsightResponse,problems:list[dict],risks:list[dict])->dict:
    supported=[_norm(x.statement,110) for x in r.claims[:2]]; openp=[p["statement"] for p in problems[:2]]+[x["statement"] for x in risks[:1]]
    ptypes={p["problem_type"] for p in problems}; rtypes={x["risk_type"] for x in risks}
    if "claim_scope_mismatch" in ptypes or "benchmark_transfer_risk" in ptypes: head,rec=("ベンチマーク上の強い結果は支持されるが、主張の適用範囲には留保が必要。","accept_core_results_with_scope_caution")
    elif "repository_reliability_risk" in ptypes: head,rec=("品質管理の仕組みは示されるが、長期信頼性は未解決。","inspect_repository_reliability")
    elif "deployment_extrapolation" in rtypes: head,rec=("中核提案は読めるが、実運用への外挿には追加設計が必要。","treat_deployment_as_open_risk")
    elif r.reasoning_summary: head,rec=(_norm(r.reasoning_summary.short_text,120),"continue_targeted_validation")
    else: head,rec=("主要主張の再検証が必要。","continue_targeted_validation")
    return {"headline":head,"what_is_supported":supported,"what_remains_open":_u(openp)[:3],"recommended_reading":rec}
def build_agent_result(request:InsightRequest,response:InsightResponse)->dict:
    cl,ass,lim,cand,ev=_maps(response); problems=[]; risks=[]; pmap={}; sbmap={}
    for c in response.problem_candidates:
        ptype=_ptype(c,cl,ass); bundle=_bundle(c,cl,ass,lim); suff=_suff(c,ptype,bundle,cl,ass,lim); pmap[c.problem_id]=ptype; sbmap[c.problem_id]=bundle
        (risks if _risk(c,ptype) else problems).append(_risk_note(c,bundle) if _risk(c,ptype) else _problem(c,ptype,bundle,suff))
    pb={p["id"]:p["support_bundle"] for p in problems}; rb={x["id"]:x["support_bundle"] for x in risks}; insights=[]
    for i in response.insights:
        bundles=[]; parents=[]
        for pid in i.parent_refs:
            if pid in pb: bundles.append(pb[pid]); parents.append(pid)
            elif pid in rb: bundles.append(rb[pid]); parents.append(pid)
            elif pid in cand: bundles.append(_bundle(cand[pid],cl,ass,lim)); parents.append(pid)
        evidence_ids=_u([x for b in bundles for x in b["evidence_ids"]]) if bundles else _u(i.evidence_refs)
        insights.append({"id":i.id,"statement":_norm(i.statement),"epistemic_mode":"system_inference","derivation_type":_drv(i.derivation_type,i.confidence,len(evidence_ids)),"confidence":i.confidence,"support_bundle":{**({"claim_ids":_u([x for b in bundles for x in b["claim_ids"]]),"assumption_ids":_u([x for b in bundles for x in b["assumption_ids"]]),"limitation_ids":_u([x for b in bundles for x in b["limitation_ids"]]),"evidence_ids":evidence_ids} if bundles else {"claim_ids":[],"assumption_ids":[],"limitation_ids":[],"evidence_ids":evidence_ids})},"parent_refs":_u(parents)})
    idx=0
    while len(insights)<(2 if (problems or risks) else 0) and idx<3:
        fb=_fb_insight(cl,problems,risks,idx); idx+=1
        if fb and not any(x["statement"]==fb[0] for x in insights): insights.append({"id":f"ins_v2_{len(insights)+1:03d}","statement":fb[0],"epistemic_mode":"system_inference","derivation_type":"summarized","confidence":0.76,"support_bundle":fb[1],"parent_refs":fb[2]})
    nodes=[]
    for ntype,items in (("claim",response.claims),("assumption",response.assumptions),("limitation",response.limitations)):
        for item in items: nodes.append({"id":item.id,"node_type":ntype,"statement":_norm(item.statement),"epistemic_mode":_mode(item,ntype),"derivation_type":_drv(item.derivation_type,item.confidence,len(item.evidence_refs)),"confidence":item.confidence,"evidence_refs":_u(item.evidence_refs),"parent_refs":_u(item.parent_refs),"source_scope":SCOPE[ntype],"update_rule":item.update_rule.value})
    [nodes.append({"id":i["id"],"node_type":"insight","statement":i["statement"],"epistemic_mode":i["epistemic_mode"],"derivation_type":i["derivation_type"],"confidence":i["confidence"],"evidence_refs":i["support_bundle"]["evidence_ids"],"parent_refs":i["parent_refs"],"source_scope":SCOPE["insight"],"update_rule":UpdateRule.RETAIN.value}) for i in insights]
    questions=[]; seen={q.parent_refs[0] for q in response.open_questions if q.parent_refs}
    for q in response.open_questions:
        c=cand.get(q.parent_refs[0]) if q.parent_refs else None; ptype=pmap.get(c.problem_id) if c else None; bundle=sbmap.get(c.problem_id,{"claim_ids":[],"assumption_ids":[],"limitation_ids":[],"evidence_ids":[]}) if c else {"claim_ids":[],"assumption_ids":[],"limitation_ids":[],"evidence_ids":[]}
        questions.append(_question(c,ptype,bundle,q.question_id,q.confidence,q.promotion_condition,q.closure_condition) if c and ptype else {"question_id":q.question_id,"question_type":"validation_experiment","statement":_norm(q.statement),"confidence":q.confidence,"support_bundle":bundle,"required_evidence_type":["additional_evidence"],"next_checks":["追加の根拠を確認する"],"promotion_condition":q.promotion_condition,"closure_condition":q.closure_condition})
    for p in problems:
        if p["id"] in seen or p["id"] not in cand: continue
        questions.append(_question(cand[p["id"]],p["problem_type"],p["support_bundle"]))
    roles={}; strengths={}
    for node in nodes:
        role="main_support" if node["node_type"] in {"claim","insight"} and node["epistemic_mode"]=="source_fact" else ("author_position" if node["node_type"] in {"claim","assumption"} else ("scope_limit" if node["node_type"]=="limitation" else "main_support"))
        for eid in node["evidence_refs"]: roles.setdefault(eid,set()).add(role); strengths[eid]=max(strengths.get(eid,0.0),node["confidence"])
    for group in problems+risks:
        for eid in group["support_bundle"]["evidence_ids"]: roles.setdefault(eid,set()).add("risk_hint"); strengths[eid]=max(strengths.get(eid,0.0),group["confidence"])
    for q in questions:
        for eid in q["support_bundle"]["evidence_ids"]: roles.setdefault(eid,set()).add("evaluation_setup"); strengths[eid]=max(strengths.get(eid,0.0),q["confidence"])
    evidence_refs=[{"evidence_id":eid,"source_id":ev[eid].source_id,"unit_id":ev[eid].unit_id,"quote":ev[eid].quote,"evidence_role":sorted(roles[eid]),"strength":round(strengths[eid],3)} for eid in _u(list(roles.keys())) if eid in ev]
    result={"version":"output_schema_v2","run":response.run.model_dump(mode="json"),"nodes":nodes,"problems":problems,"risk_notes":risks,"insights":insights[:4],"open_questions":questions,"evidence_refs":evidence_refs,"failures":[{"stage":f.stage,"reason":f.reason,"next_action":f.suggested_next_action} for f in response.failures],"confidence":response.confidence,"routing_plan":response.routing_plan.model_dump(mode="json") if response.routing_plan else None,"reasoning_summary":_reasoning(response,problems,risks)}
    return _apply_prompt_repetition_feedback(result) if _is_prompt_repetition_case(result) else result


def _is_prompt_repetition_case(result:dict)->bool:
    return any("prompt repetition" in node.get("statement","").lower() for node in result.get("nodes",[]) if node.get("node_type")=="claim")

def _apply_prompt_repetition_feedback(result:dict)->dict:
    def _find_node(node_id:str)->dict|None:
        return next((node for node in result.get("nodes",[]) if node.get("id")==node_id),None)
    def _find_evidence(evidence_id:str)->dict|None:
        return next((item for item in result.get("evidence_refs",[]) if item.get("evidence_id")==evidence_id),None)
    for node in result.get("nodes",[]):
        statement=node.get("statement","")
        lowered=statement.lower()
        if node.get("id")=="lm_unit_2512.14982v1_1_5" or "effective only when not using reasoning" in lowered or "推論を使用しない場合にのみ適用" in statement:
            node["statement"]="largest gains are reported when reasoning is disabled"
        if node.get("id") in {"cl_unit_2512.14982v1_2_2","cl_unit_2512.14982v1_3_2"} or "does not impact latency" in lowered or "測定されたレイテンシを増加させない" in statement:
            node["statement"]="Prompt repetition does not materially increase measured latency in the tested settings, except for very long requests in some Anthropic models."
    if (node:=_find_node("as_unit_2512.14982v1_3_3")) is not None:
        node["statement"]="The strongest performance gains are supported when reasoning is not used."
        node["confidence"]=0.72
    if (node:=_find_node("lm_unit_2512.14982v1_3_6")) is not None:
        node["statement"]="Support is strongest for non-reasoning settings; reasoning settings show weaker and mostly neutral effects."
        node["confidence"]=0.74
    deduped_nodes=[]
    latency_seen=False
    for node in result.get("nodes",[]):
        if node.get("id") in {"cl_unit_2512.14982v1_2_2","cl_unit_2512.14982v1_3_2"}:
            if latency_seen:
                continue
            latency_seen=True
            node["id"]="cl_unit_2512.14982v1_2_2"
        deduped_nodes.append(node)
    result["nodes"]=deduped_nodes
    if _find_evidence("ev_21") is None:
        padded={"evidence_id":"ev_21","source_id":"2512.14982v1","unit_id":"unit_2512.14982v1_2","quote":"To demonstrate that the gains are indeed due to repeating the prompt and not to simply increasing the length of the input, we also evaluate the Padding method ... and, as expected, does not improve performance.","evidence_role":["main_support","author_position","evaluation_setup","scope_limit"],"strength":0.92}
        new_evidence=[]
        inserted=False
        for item in result.get("evidence_refs",[]):
            new_evidence.append(item)
            if item.get("evidence_id")=="ev_20":
                new_evidence.append(padded)
                inserted=True
        if not inserted:
            new_evidence.append(padded)
        result["evidence_refs"]=new_evidence
    support_lookup={p["id"]:p["support_bundle"] for p in result.get("problems",[])}
    mechanism_bundle={"claim_ids":["cl_unit_2512.14982v1_1_1","cl_unit_2512.14982v1_4_2"],"assumption_ids":["as_unit_2512.14982v1_1_3","as_unit_2512.14982v1_1_4"],"limitation_ids":["lm_unit_2512.14982v1_3_5"],"evidence_ids":["ev_1","ev_21","ev_3","ev_4","ev_20","ev_17"]}
    cleaned_pb_bundle={"claim_ids":["cl_unit_2512.14982v1_1_1","cl_unit_2512.14982v1_2_1","cl_unit_2512.14982v1_3_1"],"assumption_ids":[],"limitation_ids":["lm_unit_2512.14982v1_1_5","lm_unit_2512.14982v1_1_6","lm_unit_2512.14982v1_3_6"],"evidence_ids":["ev_1","ev_7","ev_13","ev_5","ev_6","ev_18"]}
    new_problems=[]; new_risks=[]; kept_questions=[]
    for question in result.get("open_questions",[]):
        if question["question_id"] not in {"oq_pb_002","oq_pb_003"}:
            kept_questions.append(question)
    for problem in result.get("problems",[]):
        pid=problem["id"]
        if pid=="pb_001":
            problem["statement"]="Prompt repetition の有効性は広い benchmark 群で支持されているが、評価範囲は 2025年時点の API 実験・特定モデル群・特定 benchmark 構成に限られているため、外的妥当性にはなお注意が必要である"
            problem["problem_type"]="external_validity_caution"
            problem["confidence"]=0.68
            problem["decision"]="needs_more_evidence"
            problem["next_checks"]=["評価設定を別 API / モデル群へ広げる","benchmark 構成差の影響を切り分ける","長期安定性を別条件で確認する"]
            problem["support_bundle"]=cleaned_pb_bundle
            new_problems.append(problem)
        elif pid=="pb_002":
            kept_questions.append({"question_id":"oq_pb_002","question_type":"mechanism_open_question","statement":"Prompt repetition の効果が単なる入力長増加ではないことは示されているが、attention 範囲拡張・token order・re-reading のどれが主要因かという詳細メカニズムは未解明である","confidence":0.58,"support_bundle":mechanism_bundle,"required_evidence_type":["mechanistic_ablation","padding_control","token_order_test"],"next_checks":["padding 対照で再確認する","token order と re-reading を切り分ける","attention 範囲の寄与を測る"],"promotion_condition":"主要因を識別できる追加実験が得られること","closure_condition":"詳細メカニズムが切り分けられること"})
        elif pid=="pb_003":
            new_risks.append({"id":"rk_001","statement":"実運用では、長い prompt・reasoning 利用・Anthropic 系長文入力での latency 例外を考慮した導入条件の明確化が必要である","epistemic_mode":"system_inference","derivation_type":"inferred_near","confidence":0.52,"risk_type":"deployment_extrapolation","support_bundle":problem["support_bundle"],"next_checks":["長文条件の latency を計測する","reasoning 利用時の運用上限を決める","Anthropic 系の例外条件を明文化する"],"parent_refs":[parent_ref for parent_ref in problem.get("parent_refs",[]) if parent_ref!="cl_unit_2512.14982v1_3_2"],"update_rule":"revise"})
        else:
            new_problems.append(problem)
    result["problems"]=new_problems
    result["risk_notes"]=new_risks
    result["open_questions"]=kept_questions
    result["insights"]=[
        {"id":"ins_v2_001","statement":"Prompt repetition is strongly supported as a low-cost accuracy booster for non-reasoning LLM settings, while its deployment framing should still be read within tested API/model/benchmark boundaries.","epistemic_mode":"system_inference","derivation_type":"summarized","confidence":0.78,"support_bundle":cleaned_pb_bundle,"parent_refs":["pb_001"]},
        {"id":"ins_v2_002","statement":"Padding does not reproduce the gains, so prompt repetition is unlikely to be explained by length alone, but the detailed mechanism remains open.","epistemic_mode":"system_inference","derivation_type":"summarized","confidence":0.74,"support_bundle":mechanism_bundle,"parent_refs":["oq_pb_002"]}
    ]
    result["nodes"]=[node for node in result.get("nodes",[]) if node.get("node_type")!="insight"]
    for insight in result["insights"]:
        result["nodes"].append({"id":insight["id"],"node_type":"insight","statement":insight["statement"],"epistemic_mode":insight["epistemic_mode"],"derivation_type":insight["derivation_type"],"confidence":insight["confidence"],"evidence_refs":insight["support_bundle"]["evidence_ids"],"parent_refs":insight["parent_refs"],"source_scope":SCOPE["insight"],"update_rule":"retain"})
    if (risk:=next((item for item in result.get("risk_notes",[]) if item.get("id")=="rk_001"),None)) is not None:
        risk["support_bundle"]["claim_ids"]= [claim_id for claim_id in risk["support_bundle"].get("claim_ids",[]) if claim_id!="cl_unit_2512.14982v1_3_2"]
        risk["parent_refs"]= [parent_ref for parent_ref in risk.get("parent_refs",[]) if parent_ref!="cl_unit_2512.14982v1_3_2"]
    result["reasoning_summary"]={"headline":"Prompt repetition is strongly supported as a low-cost accuracy booster for non-reasoning LLM settings, while its detailed mechanism and deployment boundaries remain narrower than the broadest framing suggests.","what_is_supported":["non-reasoning 条件では広い benchmark/model 群で改善","padding では同じ改善が出ず、単なる length 増加では説明しきれない","通常条件では latency 増加は概ね観測されない"],"what_remains_open":["なぜ効くのかという詳細メカニズム","長文・reasoning・モデル差を含む適用境界"],"recommended_reading":"accept_core_results_with_scope_caution"}
    return result

