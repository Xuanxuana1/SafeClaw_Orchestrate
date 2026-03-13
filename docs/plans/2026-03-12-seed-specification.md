# OntoPlan Seed Specification

## 1. 种子到底是什么

OntoPlan 的知识库分两层，对应两种不同性质的"种子"：

| 层次 | 内容 | 通用/领域 | 变化频率 | 类比 |
|------|------|----------|---------|------|
| **T-Box（节点类型）** | 定义系统能识别哪些类型的节点、工具、能力 | 通用骨架 + 领域扩展 | 低（部署时配置，极少变动） | 数据库 schema |
| **A-Box（SOP 模板）** | 具体的工作流子图模板，带置信度和使用统计 | 纯领域特定，每家公司各自积累 | 高（随使用持续增长） | 数据库行记录 |

**关键判断：不需要通用的 A-Box 种子。** 每家公司的 SOP 差异极大（同样是"代码审查"，A 公司要求两人交叉 review，B 公司用 CI 自动检查即可），强行提供通用 SOP 模板反而会引入偏见。T-Box 则可以也应该提供通用骨架——执行模式（AUTOMATED/INTERACTIVE/APPROVAL）和工具能力绑定是跨企业共享的。

## 2. T-Box 种子：两层架构

### Layer 0: Universal Base（框架内置，不可删除）

与具体业务无关的结构性节点类型。任何企业部署都需要。

```yaml
# --- 执行模式原语 ---
SystemNode:
  QuerySourceNode:          # 注入 query 上下文的 artifacts
    output_artifacts: [动态，由 query 解析决定]
  ResultSinkNode:           # 收集最终输出
    input_artifacts: [动态，由意图决定]

InteractionNode:            # 与外部协作者的交互点
  RequestInfo:              # 请求信息并等待回复
  Notify:                   # 单向通知
  ApprovalGate:             # 审批卡点
  Escalate:                 # 异常升级

# --- 通用自动化能力 ---
AutomatedNode:
  FileDownload-Agent:       # 从云存储下载文件
    access_bindings: [OwnCloud, SharePoint, GoogleDrive, ...]
    input_artifacts: [file_path]
    output_artifacts: [local_file]

  FileUpload-Agent:         # 上传文件到云存储
    access_bindings: [OwnCloud, SharePoint, GoogleDrive, ...]
    input_artifacts: [local_file, target_path]
    output_artifacts: [upload_url]

  DataExtract-Agent:        # 从文档中提取结构化数据
    access_bindings: []     # 纯本地计算
    input_artifacts: [local_file]
    output_artifacts: [extracted_data]

  DataTransform-Agent:      # 数据清洗、合并、转换
    access_bindings: []
    input_artifacts: [extracted_data]
    output_artifacts: [transformed_data]

  ReportGenerate-Agent:     # 生成报告/表格
    access_bindings: []
    input_artifacts: [transformed_data]
    output_artifacts: [report_file]

  Coordinator-Agent:        # 路由 / 汇总
    Router-Agent
    Synthesizer-Agent
```

这些节点类型对应的是**原子能力**，不绑定任何业务语义。它们是构造任何 SOP 模板的积木。

### Layer 1: Domain Extension Pack（按行业/角色提供，可选安装）

每个扩展包补充特定领域的节点类型。企业根据自身业务选择安装哪些包。

```yaml
# === SDE Pack（软件开发） ===
SDE-Agent:
  CodeReview-Agent:
    access_bindings: [GitLab]
    input_artifacts: [mr_url]
    output_artifacts: [MR_review_result, review_comments, final_review_result]
  BugFix-Agent:
    access_bindings: [GitLab]
    input_artifacts: [issue_ref, repo_url]
    output_artifacts: [fix_commit, test_result]
  Deployment-Agent:
    access_bindings: [GitLab]
    input_artifacts: [repo_url, branch]
    output_artifacts: [deploy_status, pipeline_url]
  RepoManagement-Agent:
    access_bindings: [GitLab]
    input_artifacts: [repo_url]
    output_artifacts: [repo_metadata, file_list]

# === PM Pack（项目管理） ===
PM-Agent:
  IssueTracking-Agent:
    access_bindings: [Plane, GitLab]
    input_artifacts: [issue_ref]
    output_artifacts: [issue_status, issue_metadata]
  SprintPlanning-Agent:
    access_bindings: [Plane]
    input_artifacts: [project_ref]
    output_artifacts: [sprint_plan, task_assignments]
  StatusReport-Agent:
    access_bindings: [Plane, GitLab]
    input_artifacts: [project_ref, date_range]
    output_artifacts: [status_report]

# === HR Pack（人力资源） ===
HR-Agent:
  ResumeScreening-Agent:
    access_bindings: [OwnCloud]
    input_artifacts: [resume_files]
    output_artifacts: [screening_result, candidate_ranking]
  InterviewScheduling-Agent:
    access_bindings: [RocketChat, OwnCloud]
    input_artifacts: [candidate_list, interviewer_list]
    output_artifacts: [schedule]
  SalaryAnalysis-Agent:
    access_bindings: [OwnCloud]
    input_artifacts: [salary_data]
    output_artifacts: [analysis_report]
  AttendanceCheck-Agent:
    access_bindings: [OwnCloud, RocketChat]
    input_artifacts: [date_range, department]
    output_artifacts: [attendance_data]

# === Finance Pack（财务） ===
Finance-Agent:
  InvoiceMatching-Agent:
    access_bindings: [OwnCloud]
    input_artifacts: [invoice_files, payment_files]
    output_artifacts: [match_result, flagged_items]
  ExpenseValidation-Agent:
    access_bindings: [OwnCloud]
    input_artifacts: [expense_files, policy_rules]
    output_artifacts: [validation_result, exceptions]
  TaxCalculation-Agent:
    access_bindings: [OwnCloud]
    input_artifacts: [financial_data, tax_rules]
    output_artifacts: [tax_report]

# === DS Pack（数据科学） ===
DS-Agent:
  DataCleaning-Agent:
    access_bindings: [OwnCloud]
    input_artifacts: [raw_data_files]
    output_artifacts: [cleaned_data]
  StatAnalysis-Agent:
    access_bindings: []
    input_artifacts: [cleaned_data, analysis_spec]
    output_artifacts: [analysis_result, charts]
  Visualization-Agent:
    access_bindings: []
    input_artifacts: [data, chart_spec]
    output_artifacts: [chart_files]

# === Admin Pack（行政） ===
Admin-Agent:
  MeetingArrange-Agent:
    access_bindings: [RocketChat, OwnCloud]
    input_artifacts: [attendee_list, time_range]
    output_artifacts: [meeting_schedule, room_assignment]
  InfoCollection-Agent:
    access_bindings: [RocketChat]
    input_artifacts: [question_list, target_users]
    output_artifacts: [collected_responses]
```

### Layer 1.5: Compound Node Templates（复合节点，按需安装）

预定义的迭代流程封装，解决常见的循环工作流：

```yaml
review_request_review_loop:        # 代码审查-修复循环
  internal_fsm: REVIEWING -> REQUEST_FIX -> REVIEWING -> DONE
  max_iterations: 3

data_quality_check_loop:           # 数据质量检查-修正循环
  internal_fsm: CHECKING -> REQUEST_CORRECTION -> CHECKING -> DONE
  max_iterations: 5

approval_escalation_chain:         # 审批-升级链
  internal_fsm: REQUESTING -> WAITING -> APPROVED | ESCALATE -> REQUESTING_L2 -> DONE
  max_iterations: 3
```

## 3. A-Box 种子：纯领域特定

### 为什么不提供通用 A-Box

A-Box 是 SOP 子图模板——它编码的是"在这家公司里，做某件事的标准流程是什么"。这天然是领域特定的：

- 同一个"代码审查"流程，在不同公司里节点数量、通知对象、审批链完全不同
- 一个通用的"代码审查"模板如果置信度过高，会阻碍系统学到这家公司的真正流程
- 设计文档的三阶段生命周期本身就是为了解决 A-Box 从零积累的问题

### Phase 0 Bootstrap：种子的生成方式

A-Box 种子**不是预定义的**，而是在部署时通过 Phase 0 Bootstrap 自动生成的：

```
输入:
  1. 已安装的 T-Box (Layer 0 + 选择的 Layer 1 扩展包)
  2. 种子查询集 (见下文)

过程:
  FOR each seed_query:
      intents = LLM_extract_intents(seed_query, T_Box_schema)
      FOR i IN 1..5:
          dag = LLM_generate_dag(intents, T_Box, temperature=0.7+0.1*i)
          IF ontology_valid(dag) AND contracts_satisfied(dag):
              score = proxy_fitness(dag, intents)
              candidates.append((score, dag))
      best = top_k(candidates, k=2)
      FOR dag IN best:
          pattern = abstract_to_sop_template(dag, seed_query)
          pattern.confidence = 0.5   # 低初始置信度，等待执行验证
          pattern.origin = "bootstrap"
          KG.A_Box.add(pattern)

输出:
  A-Box 中的初始 SOP 模板集合 (每个种子查询产出 1-2 个模板)
```

### 种子查询集的来源

| 来源 | 说明 | 示例 |
|------|------|------|
| **客户提供** | 企业自身的典型任务描述 | "每周五汇总各部门的周报，合并后发给 VP" |
| **T-Box 驱动生成** | LLM 根据已安装的节点类型组合生成多样化查询 | 如果安装了 HR Pack，自动生成"筛选简历→安排面试→通知候选人" |
| **Benchmark 驱动** | TheAgentCompany 175 个 task.md（仅在评测场景） | 直接用 task.md 内容作为种子查询 |

### 种子查询覆盖要求

Phase 0 结束时应满足：

```
覆盖率检查:
  FOR each node_type IN installed_T_Box:
      IF node_type NOT IN any SOP_template:
          WARNING: node_type {name} has no coverage, generate additional seed queries

目标: 每个已安装的非系统节点类型至少出现在 3 个 SOP 模板中
```

## 4. 种子文件格式

### T-Box 扩展包格式（YAML）

```yaml
# File: tbox_packs/sde_pack.yaml
pack:
  name: "sde"
  version: "1.0"
  description: "Software Development Engineering node types"
  depends_on: ["base"]   # 依赖 Layer 0 base

node_types:
  - name: "CodeReview-Agent"
    execution_mode: "AUTOMATED"
    access_bindings: ["GitLab"]
    input_artifacts: ["mr_url"]
    output_artifacts: ["MR_review_result", "review_comments", "final_review_result"]
    keywords: ["review", "mr", "merge request", "code"]

  - name: "BugFix-Agent"
    execution_mode: "AUTOMATED"
    access_bindings: ["GitLab"]
    input_artifacts: ["issue_ref", "repo_url"]
    output_artifacts: ["fix_commit", "test_result"]
    keywords: ["bug", "fix", "patch", "debug"]
    # ...

compound_nodes:
  - name: "review_request_review_loop"
    execution_mode: "AUTOMATED"
    access_bindings: ["GitLab", "RocketChat"]
    input_artifacts: ["mr_url"]
    output_artifacts: ["final_review_result", "fix_history"]
    fsm:
      states: ["REVIEWING", "REQUEST_FIX", "DONE"]
      initial_state: "REVIEWING"
      transitions:
        - {from: "REVIEWING", to: "REQUEST_FIX", condition: "has_issues"}
        - {from: "REQUEST_FIX", to: "REVIEWING", condition: "fix_committed"}
        - {from: "REVIEWING", to: "DONE", condition: "approved"}
      max_iterations: 3
      timeout_seconds: 600
      internal_nodes:
        - {state: "REVIEWING", node_type: "CodeReview-Agent", mode: "AUTOMATED"}
        - {state: "REQUEST_FIX", node_type: "RequestInfo", mode: "INTERACTIVE",
           target_actor_role: "Developer", channel: "RocketChat"}

target_actor_roles:
  - "Developer"
  - "Tech Lead"
  - "DevOps Engineer"
```

### 种子查询集格式（YAML）

```yaml
# File: seed_queries/sde_seeds.yaml
pack: "sde"
queries:
  - text: "Review the merge request and notify the team lead if approved"
    expected_intents: ["code_review", "status_notification"]
    complexity: "simple"

  - text: "Check Sarah's MR, if code has issues ask her to fix, notify PM when done"
    expected_intents: ["code_review", "request_fix_update", "status_notification"]
    complexity: "compound"   # 涉及迭代

  - text: "Clone the bustub repo, implement HyperLogLog, run tests, push if all pass"
    expected_intents: ["repo_clone", "code_implementation", "test_execution", "code_push"]
    complexity: "sequential"

  - text: "Add CI pipeline to the project, configure lint and test stages"
    expected_intents: ["repo_management", "ci_configuration"]
    complexity: "simple"
```

## 5. 种子增长路径

```
部署时                      运行中                        成熟期
──────────────────────→──────────────────────→──────────────────────→

T-Box:                     T-Box:                       T-Box:
  Layer 0 (内置)             不变                          偶尔由管理员扩展
  + 选装 Layer 1 Pack                                     (当 A-Box 出现 ontology gap)

A-Box:                     A-Box:                       A-Box:
  空                        Phase 0 Bootstrap 生成         持续增长
                            ~50-100 个低置信度模板          高置信度模板浮现
                            ↓                             低置信度模板 deprecated
                            Phase 1 Self-Evolution         ↓
                            执行反馈强化/削弱               Phase 2 Human-in-the-Loop
                            新模式自动蒸馏入库              人类编辑 → 高质量模板
                                                          系统越用越准
```

## 6. 与 TheAgentCompany 评测的对接

评测场景下的种子策略：

```
T-Box: Layer 0 + 全部 6 个 Layer 1 Pack (SDE/PM/HR/Finance/DS/Admin)
A-Box: 从 175 个 task.md 做 Phase 0 Bootstrap
       → 每个 task.md 生成 1-2 个 SOP 模板
       → 初始约 200-350 个低置信度模板
       → 随评测执行逐步强化/削弱
```

## 7. 总结

| 问题 | 答案 |
|------|------|
| 需要通用节点还是领域节点？ | **T-Box 分两层**：通用骨架(Layer 0) + 领域扩展包(Layer 1)，按需安装 |
| 每个公司自己积累一套？ | **A-Box 是的**。SOP 模板纯领域特定，每家公司通过 3 阶段生命周期各自积累 |
| 种子从哪来？ | T-Box 由框架提供；A-Box 在部署时通过 Phase 0 Bootstrap 用 LLM 自动生成 |
| 初始置信度？ | A-Box 种子统一 0.5，等待执行验证后浮动 |
| 如何确保覆盖？ | Phase 0 结束时检查每个节点类型至少被 3 个模板覆盖 |
