const rulesContainer=document.getElementById("rulesContainer");
const manageRulesButton=document.getElementById("manageRulesButton");
const ruleManager=document.getElementById("ruleManager");
const addRuleButton=document.getElementById("addRuleButton");
const editRuleButton=document.getElementById("editRuleButton");
const deleteRuleButton=document.getElementById("deleteRuleButton");
const managerMessage=document.getElementById("managerMessage");
const ruleForm=document.getElementById("ruleForm");
const ruleId=document.getElementById("ruleId");
const ruleText=document.getElementById("ruleText");
const ruleDecision=document.getElementById("ruleDecision");
const ruleType=document.getElementById("ruleType");
const rulePriority=document.getElementById("rulePriority");
const cancelRuleButton=document.getElementById("cancelRuleButton");
const evaluateButton=document.getElementById("evaluateButton");
const resultsEmpty=document.getElementById("resultsEmpty");
const resultsTableWrapper=document.getElementById("resultsTableWrapper");
const resultsBody=document.getElementById("resultsBody");
const totalCount=document.getElementById("totalCount");
const approvedCount=document.getElementById("approvedCount");
const rejectedCount=document.getElementById("rejectedCount");
const escalatedCount=document.getElementById("escalatedCount");
const traceContainer=document.getElementById("traceContainer");
const traceHint=document.getElementById("traceHint");
let rules=[];
let selectedRuleId=null;
let evaluationResults=[];
let editingRuleId=null;
function escapeHtml(value){
    return String(value??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
}
function formatAmount(value){
    if(value===null||value===undefined||value===""){
        return "Missing";
    }
    const number=Number(value);
    if(Number.isNaN(number)){
        return "Missing";
    }
    return new Intl.NumberFormat("en-US",{style:"currency",currency:"USD"}).format(number);
}
function decisionClass(decision){
    if(decision==="APPROVE"){
        return "approve";
    }
    if(decision==="REJECT"){
        return "reject";
    }
    return "escalate";
}
function sortRules(ruleList){
    return [...ruleList].sort((a,b)=>Number(a.priority)-Number(b.priority));
}
function getNextRuleId(){
    const numbers=rules.map(rule=>{
        const match=String(rule.id||"").match(/^R(\d+)$/i);
        return match?Number(match[1]):0;
    }).filter(number=>number>0);
    const nextNumber=Math.max(0,...numbers)+1;
    return `R${nextNumber}`;
}
function renderRules(){
    const sortedRules=sortRules(rules);
    rulesContainer.innerHTML="";
    if(!sortedRules.length){
        rulesContainer.innerHTML=`<div class="empty-state">No business rules configured.</div>`;
        return;
    }
    sortedRules.forEach(rule=>{
        const card=document.createElement("div");
        card.className="rule-card selectable";
        if(selectedRuleId===rule.id){
            card.classList.add("selected");
        }
        card.dataset.ruleId=rule.id;
        card.innerHTML=`<div class="rule-header"><span class="rule-id">${escapeHtml(rule.id)}</span><span class="rule-priority">Priority ${escapeHtml(rule.priority)}</span></div><div class="rule-text">${escapeHtml(rule.rule)}</div><div class="rule-meta"><span class="rule-decision ${decisionClass(rule.decision)}">${escapeHtml(rule.decision)}</span><span class="rule-type">${escapeHtml(rule.type||"POLICY")}</span></div>`;
        card.addEventListener("click",()=>{
            selectedRuleId=rule.id;
            renderRules();
            managerMessage.textContent=`${rule.id} selected. You can edit or delete this rule.`;
        });
        rulesContainer.appendChild(card);
    });
}
async function loadRules(){
    const response=await fetch("/api/rules");
    if(!response.ok){
        throw new Error("Unable to load business rules.");
    }
    const data=await response.json();
    rules=Array.isArray(data.rules)?data.rules:[];
    renderRules();
}
function openAddForm(){
    editingRuleId=null;
    ruleForm.classList.remove("hidden");
    ruleId.value=getNextRuleId();
    ruleId.readOnly=false;
    ruleText.value="";
    ruleDecision.value="APPROVE";
    ruleType.value="POLICY";
    rulePriority.value="10";
    managerMessage.textContent="Create a new business rule.";
}
function openEditForm(){
    if(!selectedRuleId){
        managerMessage.textContent="Select a rule first.";
        return;
    }
    const rule=rules.find(item=>item.id===selectedRuleId);
    if(!rule){
        managerMessage.textContent="Selected rule could not be found.";
        return;
    }
    editingRuleId=rule.id;
    ruleForm.classList.remove("hidden");
    ruleId.value=rule.id;
    ruleId.readOnly=true;
    ruleText.value=rule.rule||"";
    ruleDecision.value=rule.decision||"ESCALATE";
    ruleType.value=rule.type||"POLICY";
    rulePriority.value=rule.priority||10;
    managerMessage.textContent=`Editing ${rule.id}.`;
}
function closeForm(){
    editingRuleId=null;
    ruleForm.classList.add("hidden");
    ruleId.readOnly=false;
}
async function saveRule(event){
    event.preventDefault();
    const id=ruleId.value.trim().toUpperCase();
    const payload={id,rule:ruleText.value.trim(),decision:ruleDecision.value,type:ruleType.value,priority:Number(rulePriority.value)};
    if(!payload.rule){
        managerMessage.textContent="Business rule cannot be empty.";
        return;
    }
    if(!Number.isInteger(payload.priority)||payload.priority<1){
        managerMessage.textContent="Priority must be a positive number.";
        return;
    }
    try{
        let response;
        if(editingRuleId){
            response=await fetch(`/api/rules/${encodeURIComponent(editingRuleId)}`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
        }else{
            response=await fetch("/api/rules",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
        }
        const data=await response.json();
        if(!response.ok){
            throw new Error(data.error||"Unable to save rule.");
        }
        selectedRuleId=data.id;
        await loadRules();
        closeForm();
        managerMessage.textContent=`${data.id} saved successfully. Policy configuration updated.`;
    }catch(error){
        managerMessage.textContent=error.message;
    }
}
async function deleteSelectedRule(){
    if(!selectedRuleId){
        managerMessage.textContent="Select a rule first.";
        return;
    }
    const confirmed=window.confirm(`Delete ${selectedRuleId}?`);
    if(!confirmed){
        return;
    }
    try{
        const response=await fetch(`/api/rules/${encodeURIComponent(selectedRuleId)}`,{method:"DELETE"});
        const data=await response.json();
        if(!response.ok){
            throw new Error(data.error||"Unable to delete rule.");
        }
        const deletedId=selectedRuleId;
        selectedRuleId=null;
        closeForm();
        await loadRules();
        managerMessage.textContent=`${deletedId} deleted successfully.`;
    }catch(error){
        managerMessage.textContent=error.message;
    }
}
function renderResults(){
    resultsBody.innerHTML="";
    evaluationResults.forEach((result,index)=>{
        const claim=result.claim;
        const row=document.createElement("tr");
        row.className="claim-row";
        row.dataset.index=index;
        row.innerHTML=`<td><strong>${escapeHtml(claim.id)}</strong></td><td>${escapeHtml(claim.employee||"Missing")}</td><td>${escapeHtml(claim.department||"Missing")}</td><td>${formatAmount(claim.amount)}</td><td><span class="decision ${decisionClass(result.decision)}">${escapeHtml(result.decision)}</span></td><td>${escapeHtml(result.matched_rule||"None")}</td>`;
        row.addEventListener("click",()=>showTrace(index));
        resultsBody.appendChild(row);
    });
    resultsEmpty.classList.add("hidden");
    resultsTableWrapper.classList.remove("hidden");
}
function showTrace(index){
    const result=evaluationResults[index];
    if(!result){
        return;
    }
    const claim=result.claim;
    document.querySelectorAll(".claim-row").forEach(row=>row.classList.remove("active"));
    const selectedRow=document.querySelector(`.claim-row[data-index="${index}"]`);
    if(selectedRow){
        selectedRow.classList.add("active");
    }
    traceHint.textContent=`${claim.id} · ${claim.employee||"Missing"}`;
    const traceItems=Array.isArray(result.trace)?result.trace:[];
    let html=`<div class="trace-card"><div class="trace-step"><span class="trace-label">CLAIM</span><h3>${escapeHtml(claim.id)}</h3><p><strong>Name:</strong> ${escapeHtml(claim.employee||"Missing")}<br><strong>Department:</strong> ${escapeHtml(claim.department||"Missing")}<br><strong>Amount:</strong> ${formatAmount(claim.amount)}<br><strong>Description:</strong> ${escapeHtml(claim.description||"Missing")}</p></div><div class="trace-arrow">↓</div>`;
    traceItems.forEach((item,itemIndex)=>{
        const isMatched=item.status==="MATCHED";
        html+=`<div class="trace-step ${isMatched?"rationale":""}"><span class="trace-label">RULE ${itemIndex+1}</span><h3>${escapeHtml(item.ruleId)} <span class="trace-status ${isMatched?"matched":"not-matched"}">${escapeHtml(item.status)}</span></h3><p>${escapeHtml(item.rule)}</p><small>${escapeHtml(item.reason)}</small></div>`;
        if(itemIndex<traceItems.length-1){
            html+=`<div class="trace-arrow">↓</div>`;
        }
    });
    html+=`<div class="trace-arrow">↓</div><div class="trace-step rationale"><span class="trace-label">FINAL DECISION</span><h3 class="${decisionClass(result.decision)}">${escapeHtml(result.decision)}</h3><p>Matched rule: <strong>${escapeHtml(result.matched_rule||"None")}</strong></p><p>${escapeHtml(result.matched_rule_text||"No matching rule")}</p></div></div>`;
    traceContainer.innerHTML=html;
}
async function evaluateClaims(){
    evaluateButton.disabled=true;
    evaluateButton.textContent="Evaluating...";
    try{
        const response=await fetch("/api/evaluate",{method:"POST"});
        const data=await response.json();
        if(!response.ok){
            throw new Error(data.error||"Unable to evaluate claims.");
        }
        evaluationResults=Array.isArray(data.results)?data.results:[];
        const summary=data.summary||{};
        totalCount.textContent=summary.total??0;
        approvedCount.textContent=summary.approved??0;
        rejectedCount.textContent=summary.rejected??0;
        escalatedCount.textContent=summary.escalated??0;
        renderResults();
        traceHint.textContent="Select a claim to view its decision trace.";
        traceContainer.innerHTML=`<div class="empty-state">Select a claim row above to see the decision path.</div>`;
    }catch(error){
        window.alert(error.message);
    }finally{
        evaluateButton.disabled=false;
        evaluateButton.textContent="Evaluate Claims";
    }
}
manageRulesButton.addEventListener("click",()=>{
    ruleManager.classList.toggle("hidden");
    if(!ruleManager.classList.contains("hidden")){
        managerMessage.textContent="Select a rule to edit or delete it.";
    }
});
addRuleButton.addEventListener("click",openAddForm);
editRuleButton.addEventListener("click",openEditForm);
deleteRuleButton.addEventListener("click",deleteSelectedRule);
cancelRuleButton.addEventListener("click",closeForm);
ruleForm.addEventListener("submit",saveRule);
evaluateButton.addEventListener("click",evaluateClaims);
async function initialize(){
    try{
        await loadRules();
    }catch(error){
        rulesContainer.innerHTML=`<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
}
initialize();