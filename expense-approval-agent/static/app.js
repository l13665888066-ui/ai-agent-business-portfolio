const state = {
  userId: "E1001",
  identity: null,
  attachment: null,
  resubmitId: null,
};

const statusLabels = {
  approved: "已通过",
  pending_manager: "待主管审批",
  pending_finance: "待财务审批",
  returned: "已退回",
  rejected: "已驳回",
};

const actionLabels = {
  submit: "提交申请",
  resubmit: "重新提交",
  approve: "审批同意",
  return: "退回补充",
  reject: "审批驳回",
};

const roleLabels = {
  employee: "员工",
  manager: "主管",
  finance: "财务",
};

const qs = (selector) => document.querySelector(selector);
const qsa = (selector) => [...document.querySelectorAll(selector)];

async function api(path, options = {}) {
  const headers = {
    "X-User-Id": state.userId,
    ...(options.headers || {}),
  };
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { ...options, headers });
  const data = await response.json().catch(() => ({
    success: false,
    message: "服务返回了无法解析的结果",
  }));
  if (!response.ok) {
    const error = new Error(data.message || data.reasons?.[0] || "请求失败");
    error.data = data;
    error.status = response.status;
    throw error;
  }
  return data;
}

function showToast(message) {
  const toast = qs("#toast");
  toast.textContent = message;
  toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add("hidden"), 2600);
}

function statusBadge(status) {
  return `<span class="status ${status}">${statusLabels[status] || status}</span>`;
}

function money(value) {
  return Number(value).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

async function loadIdentities() {
  const data = await api("/api/demo-identities");
  const select = qs("#identity-select");
  select.innerHTML = data.identities.map((item) => (
    `<option value="${item.user_id}">${item.name} · ${roleLabels[item.role]}</option>`
  )).join("");
  select.value = state.userId;
}

async function loadSession() {
  const data = await api(`/api/session?user_id=${encodeURIComponent(state.userId)}`);
  state.identity = data.identity;
  const identity = data.identity;
  qs("#profile-card").innerHTML = `
    <div class="profile-item"><span>申请人</span><strong>${identity.name}</strong></div>
    <div class="profile-item"><span>员工编号</span><strong>${identity.user_id}</strong></div>
    <div class="profile-item"><span>所属部门</span><strong>${identity.department}</strong></div>
    <div class="profile-item"><span>直属主管</span><strong>${identity.manager_id || "不适用"}</strong></div>
  `;
  const canSubmit = data.permissions.can_submit;
  qs("#expense-form").classList.toggle("hidden", !canSubmit);
  qs("#profile-card").classList.toggle("hidden", !canSubmit);
  qs("#submit-view .section-head").classList.toggle("hidden", !canSubmit);
  if (!canSubmit && qs("#submit-view").classList.contains("active")) {
    switchTab("pending");
  }
  const descriptions = {
    employee: "展示被退回、需要本人补充材料的申请。",
    manager: "仅展示当前主管名下等待审批的申请。",
    finance: "展示等待财务复核的申请。",
  };
  qs("#pending-description").textContent = descriptions[identity.role];
}

function switchTab(tabName) {
  qsa(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === tabName);
  });
  qsa(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `${tabName}-view`);
  });
  if (tabName === "pending") loadApplications("pending");
  if (tabName === "records") loadApplications("all");
}

function renderApplicationList(items, target) {
  const element = qs(target);
  if (!items.length) {
    element.innerHTML = `<div class="empty-state">当前没有需要展示的申请</div>`;
    return;
  }
  element.innerHTML = items.map((item) => `
    <button class="application-card" data-application-id="${item.id}">
      <div><small>申请单</small><br><strong>#${item.id}</strong></div>
      <div>
        <strong>${item.expense_type}</strong><br>
        <small>${item.applicant_name} · ${item.department} · ${item.created_at}</small>
      </div>
      <div class="money">¥ ${money(item.amount)}</div>
      ${statusBadge(item.status)}
      <span class="chevron">›</span>
    </button>
  `).join("");
  element.querySelectorAll(".application-card").forEach((button) => {
    button.addEventListener("click", () => openDetail(button.dataset.applicationId));
  });
}

async function loadApplications(scope) {
  const target = scope === "pending" ? "#pending-list" : "#records-list";
  qs(target).innerHTML = `<div class="empty-state">正在加载...</div>`;
  try {
    const data = await api(`/api/applications?scope=${scope}`);
    renderApplicationList(data.applications, target);
    if (scope === "pending") {
      qs("#pending-count").textContent = data.applications.length || "";
    }
  } catch (error) {
    qs(target).innerHTML = `<div class="empty-state">${error.message}</div>`;
  }
}

function renderDecision(decision, isError = false) {
  const panel = qs("#decision-panel");
  panel.classList.remove("hidden");
  panel.classList.toggle("error", isError || !decision.success);
  const sources = (decision.policy_sources || []).map((source) => (
    `<li>${source.title}（${source.retrieval_mode === "vector" ? "向量检索" : "本地兜底"}）</li>`
  )).join("");
  const semantic = decision.semantic_review || {};
  panel.innerHTML = `
    ${statusBadge(decision.status)}
    <h3>${decision.decision}</h3>
    <p>风险等级：${decision.risk_level}</p>
    <ul>${(decision.reasons || []).map((item) => `<li>${item}</li>`).join("")}</ul>
    ${decision.missing_fields?.length ? `<p><strong>需要补充：</strong>${decision.missing_fields.join("、")}</p>` : ""}
    <p><strong>下一步：</strong>${decision.next_step}</p>
    <p><strong>审批单号：</strong>${decision.application_id ? `#${decision.application_id}` : "未生成"}</p>
    ${semantic.summary ? `<p><strong>AI材料提示：</strong>${semantic.summary}</p>` : ""}
    ${semantic.suggestions?.length ? `<ul>${semantic.suggestions.map((item) => `<li>${item}</li>`).join("")}</ul>` : ""}
    ${sources ? `<p><strong>制度依据：</strong></p><ul>${sources}</ul>` : ""}
  `;
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function uploadAttachmentIfNeeded() {
  const fileInput = qs("#attachment");
  const file = fileInput.files[0];
  if (!file) return state.attachment;
  const formData = new FormData();
  formData.append("file", file);
  const data = await api("/api/attachments", { method: "POST", body: formData });
  state.attachment = data.attachment;
  qs("#attachment-status").textContent = `已上传：${data.attachment.name}`;
  return state.attachment;
}

function formPayload() {
  const data = Object.fromEntries(new FormData(qs("#expense-form")));
  if (state.attachment) {
    data.attachment_id = state.attachment.attachment_id;
    data.attachment_name = state.attachment.name;
  }
  return data;
}

async function submitExpense(event) {
  event.preventDefault();
  const button = qs("#submit-button");
  button.disabled = true;
  button.textContent = state.resubmitId ? "重新提交中..." : "预审中...";
  try {
    await uploadAttachmentIfNeeded();
    const path = state.resubmitId
      ? `/api/applications/${state.resubmitId}/resubmit`
      : "/api/applications";
    const decision = await api(path, {
      method: "POST",
      body: JSON.stringify(formPayload()),
    });
    renderDecision(decision);
    showToast(state.resubmitId ? "申请已重新提交" : "申请已提交");
    state.resubmitId = null;
    qs("#submit-button").textContent = "提交预审";
    await Promise.all([loadApplications("pending"), loadApplications("all")]);
  } catch (error) {
    renderDecision(error.data || {
      success: false,
      status: "returned",
      decision: "提交失败",
      risk_level: "中",
      reasons: [error.message],
      next_step: "检查材料后重试",
    }, true);
  } finally {
    button.disabled = false;
    button.textContent = state.resubmitId ? "重新提交申请" : "提交预审";
  }
}

function resetForm() {
  qs("#expense-form").reset();
  qs("#expense-date").max = new Date().toISOString().slice(0, 10);
  state.attachment = null;
  state.resubmitId = null;
  qs("#attachment-status").textContent = "支持PDF、PNG、JPG、JPEG，单个文件不超过5MB。";
  qs("#submit-button").textContent = "提交预审";
  qs("#decision-panel").classList.add("hidden");
}

function detailGrid(application) {
  return `
    <div class="detail-grid">
      <div class="detail-item"><span>申请人</span><strong>${application.applicant_name}</strong></div>
      <div class="detail-item"><span>部门</span><strong>${application.department}</strong></div>
      <div class="detail-item"><span>金额</span><strong>¥ ${money(application.amount)}</strong></div>
      <div class="detail-item"><span>费用类型</span><strong>${application.expense_type}</strong></div>
      <div class="detail-item"><span>发生日期</span><strong>${application.expense_date}</strong></div>
      <div class="detail-item"><span>当前状态</span>${statusBadge(application.status)}</div>
    </div>
  `;
}

function renderTimeline(actions) {
  if (!actions.length) return `<p>暂无审批动作。</p>`;
  return `<ul class="timeline">${actions.map((action) => `
    <li>
      <strong>${actionLabels[action.action] || action.action}</strong>
      <div>${action.comment}</div>
      <small>${action.actor_id} · ${roleLabels[action.actor_role] || action.actor_role} · ${action.created_at}</small>
    </li>
  `).join("")}</ul>`;
}

function renderPolicySources(sources) {
  if (!sources?.length) return `<p>未检索到可靠制度依据。</p>`;
  return sources.map((source) => `
    <div class="policy-source">
      <strong>${source.title} · ${source.retrieval_mode === "vector" ? "向量检索" : "本地兜底"}</strong>
      <p>${source.excerpt}</p>
    </div>
  `).join("");
}

async function openDetail(applicationId) {
  try {
    const data = await api(`/api/applications/${applicationId}`);
    const app = data.application;
    qs("#detail-title").textContent = `申请单 #${app.id}`;
    const semantic = app.semantic_review || {};
    qs("#detail-content").innerHTML = `
      ${detailGrid(app)}
      <div class="detail-section">
        <h3>报销说明</h3>
        <p>${app.purpose}</p>
        <p><strong>发票号码：</strong>${app.invoice_no}</p>
        <p><strong>附件：</strong>${app.attachment_name || "未上传"}</p>
      </div>
      <div class="detail-section">
        <h3>预审结论</h3>
        <p><strong>${app.decision}</strong> · 风险等级${app.risk_level}</p>
        ${semantic.summary ? `<p><strong>AI材料摘要：</strong>${semantic.summary}</p>` : ""}
        ${semantic.risk_hints?.length ? `<ul>${semantic.risk_hints.map((item) => `<li>${item}</li>`).join("")}</ul>` : ""}
      </div>
      <div class="detail-section">
        <h3>制度依据</h3>
        ${renderPolicySources(app.policy_sources)}
      </div>
      <div class="detail-section">
        <h3>审批时间线</h3>
        ${renderTimeline(data.actions)}
      </div>
      ${data.permissions.can_act ? `
        <div class="detail-section approval-box">
          <h3>审批处理</h3>
          <textarea id="approval-comment" placeholder="退回或驳回时必须填写审批意见"></textarea>
          <div class="approval-actions">
            <button class="button danger" data-action="reject">驳回</button>
            <button class="button warning" data-action="return">退回补充</button>
            <button class="button primary" data-action="approve">同意</button>
          </div>
        </div>
      ` : ""}
      ${data.permissions.can_resubmit ? `
        <div class="detail-section">
          <button class="button primary" id="load-resubmit">补充材料并重新提交</button>
        </div>
      ` : ""}
    `;
    qsa("[data-action]").forEach((button) => {
      button.addEventListener("click", () => performAction(app.id, button.dataset.action));
    });
    qs("#load-resubmit")?.addEventListener("click", () => loadForResubmit(app));
    qs("#detail-dialog").showModal();
  } catch (error) {
    showToast(error.message);
  }
}

async function performAction(applicationId, action) {
  const comment = qs("#approval-comment")?.value.trim() || "";
  try {
    await api(`/api/applications/${applicationId}/actions`, {
      method: "POST",
      body: JSON.stringify({ action, comment }),
    });
    showToast("审批结果已写入");
    qs("#detail-dialog").close();
    await Promise.all([loadApplications("pending"), loadApplications("all")]);
  } catch (error) {
    showToast(error.message);
  }
}

function loadForResubmit(application) {
  state.resubmitId = application.id;
  state.attachment = application.attachment_id ? {
    attachment_id: application.attachment_id,
    name: application.attachment_name,
  } : null;
  qs("#expense-type").value = application.expense_type;
  qs("#amount").value = application.amount;
  qs("#invoice-no").value = application.invoice_no;
  qs("#expense-date").value = application.expense_date;
  qs("#purpose").value = application.purpose;
  qs("#attachment-status").textContent = state.attachment
    ? `沿用附件：${state.attachment.name}`
    : "支持PDF、PNG、JPG、JPEG，单个文件不超过5MB。";
  qs("#submit-button").textContent = "重新提交申请";
  qs("#detail-dialog").close();
  switchTab("submit");
  qs("#expense-form").scrollIntoView({ behavior: "smooth" });
}

async function switchIdentity(userId) {
  state.userId = userId;
  state.attachment = null;
  state.resubmitId = null;
  qs("#decision-panel").classList.add("hidden");
  await loadSession();
  await Promise.all([loadApplications("pending"), loadApplications("all")]);
}

async function initialize() {
  qs("#expense-date").max = new Date().toISOString().slice(0, 10);
  await loadIdentities();
  await switchIdentity(state.userId);
}

qsa(".tab").forEach((tab) => tab.addEventListener("click", () => switchTab(tab.dataset.tab)));
qsa(".refresh-list").forEach((button) => button.addEventListener("click", () => loadApplications(button.dataset.scope)));
qs("#identity-select").addEventListener("change", (event) => switchIdentity(event.target.value));
qs("#expense-form").addEventListener("submit", submitExpense);
qs("#reset-form").addEventListener("click", resetForm);
qs("#close-detail").addEventListener("click", () => qs("#detail-dialog").close());

initialize().catch((error) => showToast(error.message));
