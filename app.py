from flask import Flask,jsonify,request,send_from_directory
import json
import os
import re
from threading import Lock
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
RULES_FILE=os.path.join(BASE_DIR,"rules.json")
CLAIMS_FILE=os.path.join(BASE_DIR,"claims.json")
app=Flask(__name__)
file_lock=Lock()
def read_json(path):
    with file_lock:
        with open(path,"r",encoding="utf-8") as file:
            return json.load(file)
def write_json(path,data):
    with file_lock:
        with open(path,"w",encoding="utf-8") as file:
            json.dump(data,file,indent=2,ensure_ascii=False)
def get_rules():
    data=read_json(RULES_FILE)
    return data.get("rules",[])
def get_claims():
    data=read_json(CLAIMS_FILE)
    return data.get("claims",[])
def parse_money(value):
    if value is None:
        return None
    text=str(value).replace(",","").replace("$","").strip()
    try:
        return float(text)
    except ValueError:
        return None
def extract_condition(rule_text):
    text=rule_text.lower().replace(",","")
    between_match=re.search(r"\bbetween\s+\$?(\d+(?:\.\d+)?)\s+and\s+\$?(\d+(?:\.\d+)?)",text)
    if between_match:
        return {"type":"between","minimum":float(between_match.group(1)),"maximum":float(between_match.group(2))}
    up_to_match=re.search(r"\bup\s+to\s+\$?(\d+(?:\.\d+)?)",text)
    if up_to_match:
        return {"type":"up_to","maximum":float(up_to_match.group(1))}
    under_match=re.search(r"\bunder\s+\$?(\d+(?:\.\d+)?)",text)
    if under_match:
        return {"type":"under","maximum":float(under_match.group(1))}
    above_match=re.search(r"\babove\s+\$?(\d+(?:\.\d+)?)",text)
    if above_match:
        return {"type":"above","minimum":float(above_match.group(1))}
    over_match=re.search(r"\bover\s+\$?(\d+(?:\.\d+)?)",text)
    if over_match:
        return {"type":"above","minimum":float(over_match.group(1))}
    return None
def extract_department(rule_text):
    text=rule_text.strip()
    match=re.search(r"\bfor\s+([A-Za-z][A-Za-z ]*?)(?:\s*$|\s+department\s*$)",text,re.IGNORECASE)
    if not match:
        return None
    department=match.group(1).strip()
    if department.lower() in {"any","all"}:
        return None
    return department
def condition_matches(condition,amount):
    if condition is None or amount is None:
        return False
    if condition["type"]=="up_to":
        return amount<=condition["maximum"]
    if condition["type"]=="under":
        return amount<condition["maximum"]
    if condition["type"]=="above":
        return amount>condition["minimum"]
    if condition["type"]=="between":
        return amount>=condition["minimum"] and amount<=condition["maximum"]
    return False
def rule_matches(rule,claim):
    if str(rule.get("type","POLICY")).upper()=="FALLBACK":
        return False,"Fallback rules are only used when no policy matches."
    amount=parse_money(claim.get("amount"))
    department=claim.get("department")
    if amount is None:
        return False,"Claim amount is missing or invalid."
    if not department:
        return False,"Claim department is missing."
    condition=extract_condition(rule.get("rule",""))
    if condition is None:
        return False,"Rule condition could not be understood."
    if not condition_matches(condition,amount):
        if condition["type"]=="up_to":
            return False,f"Amount ${amount:,.2f} is greater than the ${condition['maximum']:,.2f} limit."
        if condition["type"]=="under":
            return False,f"Amount ${amount:,.2f} is not under ${condition['maximum']:,.2f}."
        if condition["type"]=="above":
            return False,f"Amount ${amount:,.2f} is not above ${condition['minimum']:,.2f}."
        if condition["type"]=="between":
            return False,f"Amount ${amount:,.2f} is outside the ${condition['minimum']:,.2f} to ${condition['maximum']:,.2f} range."
        return False,"Amount does not satisfy the rule condition."
    rule_department=extract_department(rule.get("rule",""))
    if rule_department and rule_department.lower()!=str(department).strip().lower():
        return False,f"Department does not match; rule applies to {rule_department}."
    if condition["type"]=="up_to":
        condition_text=f"amount <= ${condition['maximum']:,.2f}"
    elif condition["type"]=="under":
        condition_text=f"amount < ${condition['maximum']:,.2f}"
    elif condition["type"]=="above":
        condition_text=f"amount > ${condition['minimum']:,.2f}"
    elif condition["type"]=="between":
        condition_text=f"amount between ${condition['minimum']:,.2f} and ${condition['maximum']:,.2f}"
    else:
        condition_text="amount condition"
    if rule_department:
        return True,f"Claim matches {condition_text} and department is {department}."
    return True,f"Claim matches {condition_text}; rule applies to any department."
def validate_rule_text(rule_text,rule_type):
    if not rule_text.strip():
        return False,"Business rule cannot be empty."
    if str(rule_type).upper()=="FALLBACK":
        return True,"Fallback rule accepted."
    condition=extract_condition(rule_text)
    if condition is None:
        return False,"Rule could not be understood. Use phrases such as under $X, up to $X, above $X, or between $X and $Y."
    return True,"Rule understood successfully."
def evaluate_claim(claim,rules):
    required_fields=[claim.get("id"),claim.get("employee"),claim.get("department"),claim.get("amount"),claim.get("description")]
    incomplete=any(value is None or str(value).strip()=="" for value in required_fields)
    sorted_rules=sorted(rules,key=lambda rule:int(rule.get("priority",999999)))
    trace=[]
    if incomplete:
        fallback=next((rule for rule in sorted_rules if str(rule.get("type","")).upper()=="FALLBACK"),None)
        if fallback:
            trace.append({"ruleId":fallback.get("id"),"rule":fallback.get("rule"),"status":"MATCHED","reason":"Claim is incomplete, so the fallback rule was applied."})
            return {"decision":fallback.get("decision","ESCALATE"),"matched_rule":fallback.get("id"),"matched_rule_text":fallback.get("rule"),"trace":trace}
    for rule in sorted_rules:
        if str(rule.get("type","POLICY")).upper()=="FALLBACK":
            continue
        matches,reason=rule_matches(rule,claim)
        trace.append({"ruleId":rule.get("id"),"rule":rule.get("rule"),"status":"MATCHED" if matches else "NOT MATCHED","reason":reason})
        if matches:
            return {"decision":rule.get("decision","ESCALATE"),"matched_rule":rule.get("id"),"matched_rule_text":rule.get("rule"),"trace":trace}
    fallback=next((rule for rule in sorted_rules if str(rule.get("type","")).upper()=="FALLBACK"),None)
    if fallback:
        trace.append({"ruleId":fallback.get("id"),"rule":fallback.get("rule"),"status":"MATCHED","reason":"No policy rule matched the claim, so the fallback rule was applied."})
        return {"decision":fallback.get("decision","ESCALATE"),"matched_rule":fallback.get("id"),"matched_rule_text":fallback.get("rule"),"trace":trace}
    return {"decision":"ESCALATE","matched_rule":None,"matched_rule_text":"No matching rule","trace":trace}
@app.route("/")
def index():
    return send_from_directory(BASE_DIR,"index.html")
@app.route("/style.css")
def style():
    return send_from_directory(BASE_DIR,"style.css")
@app.route("/script.js")
def script():
    return send_from_directory(BASE_DIR,"script.js")
@app.route("/rules.json")
def rules_file():
    return send_from_directory(BASE_DIR,"rules.json")
@app.route("/claims.json")
def claims_file():
    return send_from_directory(BASE_DIR,"claims.json")
@app.route("/api/rules",methods=["GET"])
def api_get_rules():
    return jsonify({"rules":get_rules()})
@app.route("/api/rules",methods=["POST"])
def api_add_rule():
    data=request.get_json(silent=True) or {}
    rule_text=str(data.get("rule","")).strip()
    decision=str(data.get("decision","ESCALATE")).upper()
    rule_type=str(data.get("type","POLICY")).upper()
    try:
        priority=int(data.get("priority",10))
    except (TypeError,ValueError):
        return jsonify({"error":"Priority must be a number."}),400
    if not rule_text:
        return jsonify({"error":"Business rule is required."}),400
    if decision not in {"APPROVE","REJECT","ESCALATE"}:
        return jsonify({"error":"Invalid decision."}),400
    if rule_type not in {"POLICY","FALLBACK"}:
        return jsonify({"error":"Invalid rule type."}),400
    valid_rule,validation_message=validate_rule_text(rule_text,rule_type)
    if not valid_rule:
        return jsonify({"error":validation_message}),400
    if priority<1:
        return jsonify({"error":"Priority must be a positive number."}),400
    rules=get_rules()
    requested_id=str(data.get("id","")).strip().upper()
    if requested_id:
        rule_id=requested_id
    else:
        numbers=[]
        for rule in rules:
            match=re.fullmatch(r"R(\d+)",str(rule.get("id","")).upper())
            if match:
                numbers.append(int(match.group(1)))
        next_number=max(numbers,default=0)+1
        rule_id=f"R{next_number}"
    if any(str(rule.get("id","")).upper()==rule_id for rule in rules):
        return jsonify({"error":f"Rule {rule_id} already exists."}),400
    new_rule={"id":rule_id,"priority":priority,"rule":rule_text,"decision":decision,"type":rule_type}
    rules.append(new_rule)
    write_json(RULES_FILE,{"rules":rules})
    return jsonify(new_rule),201
@app.route("/api/rules/<rule_id>",methods=["PUT"])
def api_update_rule(rule_id):
    data=request.get_json(silent=True) or {}
    rules=get_rules()
    target=None
    for rule in rules:
        if str(rule.get("id","")).upper()==rule_id.upper():
            target=rule
            break
    if target is None:
        return jsonify({"error":"Rule not found."}),404
    rule_text=str(data.get("rule","")).strip()
    decision=str(data.get("decision",target.get("decision","ESCALATE"))).upper()
    rule_type=str(data.get("type",target.get("type","POLICY"))).upper()
    try:
        priority=int(data.get("priority",target.get("priority",10)))
    except (TypeError,ValueError):
        return jsonify({"error":"Priority must be a number."}),400
    if not rule_text:
        return jsonify({"error":"Business rule is required."}),400
    if decision not in {"APPROVE","REJECT","ESCALATE"}:
        return jsonify({"error":"Invalid decision."}),400
    if rule_type not in {"POLICY","FALLBACK"}:
        return jsonify({"error":"Invalid rule type."}),400
    valid_rule,validation_message=validate_rule_text(rule_text,rule_type)
    if not valid_rule:
        return jsonify({"error":validation_message}),400
    if priority<1:
        return jsonify({"error":"Priority must be a positive number."}),400
    target["priority"]=priority
    target["rule"]=rule_text
    target["decision"]=decision
    target["type"]=rule_type
    write_json(RULES_FILE,{"rules":rules})
    return jsonify(target)
@app.route("/api/rules/<rule_id>",methods=["DELETE"])
def api_delete_rule(rule_id):
    rules=get_rules()
    updated_rules=[rule for rule in rules if str(rule.get("id","")).upper()!=rule_id.upper()]
    if len(updated_rules)==len(rules):
        return jsonify({"error":"Rule not found."}),404
    write_json(RULES_FILE,{"rules":updated_rules})
    return jsonify({"success":True})
@app.route("/api/evaluate",methods=["POST"])
def api_evaluate():
    claims=get_claims()
    rules=get_rules()
    results=[]
    for claim in claims:
        evaluation=evaluate_claim(claim,rules)
        results.append({"claim":claim,"decision":evaluation["decision"],"matched_rule":evaluation["matched_rule"],"matched_rule_text":evaluation["matched_rule_text"],"trace":evaluation["trace"]})
    approved=sum(1 for result in results if result["decision"]=="APPROVE")
    rejected=sum(1 for result in results if result["decision"]=="REJECT")
    escalated=sum(1 for result in results if result["decision"]=="ESCALATE")
    return jsonify({"results":results,"summary":{"total":len(results),"approved":approved,"rejected":rejected,"escalated":escalated}})
if __name__=="__main__":
    app.run(debug=True)