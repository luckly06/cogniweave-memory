[English](note.en.md) | [中文](note.md)

![alt text](./image.png)
- 低代码平台，如coze【只是native RAG】；
- 普通RAG只搞知识库【减少常见幻觉做法:markdown是表格，需要转换为html的table来处理】（不否定主流调用框架langchain和开发框架langraph好用）；
## 前言：模型底层发展缺陷是“猜答案”而不是“解”答案。

框架专注于"理解业务【需靠产品】和“弥补模型“解答案”的先天性缺失””

⭐难点： 多通道系统的难点，从来不是“分数怎么对齐”，而是“不同记忆在什么时候应该被相信”
方案：
上下文工程：基于一切输入皆为提示词，框架分为多通道(检索，按不同内容进不同通道(可单进/多进)，每轮循环进对应通道数据库，实现信息自适应管理。，新机制： ** “理解任务 → 分类召回 → 跨通道融合 → 动态注入 → 自适应固化 → 生命周期治理 → 反馈调优”**

⭐难点:问题不在流程设计本身，而在于：路径假设与现实复杂性之间的差距
方案：
## 一，控制路径本质是把生成过程变成有约束的搜索过程，其他筛选出的方案：
### 如：做我现在v0.3的不同方向【重构v0.3版（Context-v0.1版）是上下文工程下的精进】。
“各记忆通道改参数”可按需更改。
- 可用于做放工具的【产品化面向cli的】，CLI 工具型产品（如 coding agent）。
```markdown
 本地 Memory 通道：
        - Semantic Memory（事实 / 知识）
        - Episodic Memory（历史轨迹）
        - Perceptual Memory（感知输入，如 OCR / UI / logs）

    工具 / 能力通道：
        - 本地 CLI 工具（git / python / custom-cli）
        - API（搜索 / DB）
        - MCP Tools（标准化工具）
        - 外部 Agent（作为 Retriever / 子代理）
        - 远程 CLI（SSH / 容器 / 云函数）
略      

```
  
- 多 Agent 协作系统/Agent + 工具混合执行系统：
```markdown
多 Agent 编排（Ralph Loop / harness agent）
Repo 作为记录系统（agent.md / ARCHITECTURE.md / PLAN.md）
端到端契约一致性。（输入输出结构稳定）

eg:参考cc源码(claude code);
  港大开源的框架openharness(前端React渲染了一下cli界面的“claide code蒸馏版”)；
  字节开源的DeerFlow - 2.0（多 Agent 流式执行）
```

- 处理自动化办公（参考 openclaw / harness-agent）等
```markdown
有新想法：嵌入【女娲skill】[Skill Layer（可复用任务单元）]

```

做框架做着做着依旧回到符号主义遇到的问题：动态的世界不好“解”【解决问题需要将解决方案和问题域特性结合起来】,技术手段难以达到期望状况。

### 欢迎小伙伴们给出建议，于是把此版本开源出去，用于框架可扩展性
![alt text](./image-1.png)
## 二，多通道认知记忆系统通过任务感知和记忆类型区分，实现信息自适应管理，本质拆成五点：
1. 多通道存储
  - 将信息分类存储为 Key / Semantic / Episodic / Perceptual / Experience / Sensory Buffer
  - 类比：就像把工具分门别类放进不同的抽屉，方便按用途拿取
![alt text](./image-2.png)
2. 任务驱动召回与融合
  - 输入经过 Modality & Task Router 判断类型和复杂度
  - 并行召回各通道候选，通道内 Rerank，跨通道 Normalize
  - 类比：类似不同专家给意见，然后统一打分融合
3. 上下文编排与工作记忆注入
  - 去重、冲突检测、压缩、结构化
  - 强制注入关键记忆，检索注入候选
  - 类比：会议纪要，把重要结论先放上桌，其余按需引用
![alt text](./image-3.png)
4. 记忆固化与抽象
  - 根据重要性、新颖性、一致性将记忆写入长期存储
  - 各通道记忆遵循不同的生命周期策略
  - 类比：整理笔记，重复、高价值的放进核心笔记本，其余归档或丢弃
5. 自适应反馈闭环
  - 收集反馈、更新策略、Promote/Demote记忆
  - 系统通过使用效果调整通道权重、写入策略和召回规模
  - 类比：学习型助理，根据你常用和有用的内容优化下次行为

## 三，文本流程图和泳道图
```markdown
============================================================
多通道认知记忆系统（打补丁后的完整流程）
目标：自适应记忆系统 + 具备学习能力的智能系统
============================================================

【0. Storage Layer：底层记忆存储层】
------------------------------------------------------------
A. Key Memory（高优先级关键事实，强制注入）
   - 形式：KV / JSON / NoSQL
   - 内容：
     * 用户稳定偏好
     * 用户身份信息
     * 长期规则 / 禁忌 / 固定约束
     * 系统级行为准则 
   - 特点：
     * 小而稳定
     * 默认高优先级
     * 不走普通RAG排序，直接参与上下文构建
   - Forget策略：
     * 默认不自动删除
     * 允许显式forget / demote
     * 可设置 pinned=True 防止自动遗忘

B. Semantic Memory（语义记忆）
   - 形式：Graph + Vector（Neo4j + Qdrant）
   - 内容：
     * 事实、概念、规则、知识点
     * 用户领域知识
     * 项目文档、规范、API知识
   - 特点：
     * 面向“知道什么”
   - Forget策略：
     * 根据重要性、访问频率、最近使用时间做保留/归档/删除
     * 重复语义项可做摘要合并或归档

C. Episodic Memory（情景记忆）
   - 形式：Timeline + Summary + Vector（SQLite + Qdrant）
   - 内容：
     * 过去发生过什么
     * 历史任务摘要
     * 关键对话事件
   - 特点：
     * 面向“发生过什么”
   - Forget策略：
     * 更依赖时效衰减
     * 过期片段优先 summary_then_delete 或 archive

D. Perceptual Memory（感知记忆）
   - 形式：Metadata + Vector（SQLite + Qdrant）
   - 说明：
     * Qdrant里存感知向量
     * SQLite里存对象、区域、来源、时间等元数据
     * 若 embedder 是图像/多模态编码器，则可视作当前工程实现中的“Multimodal Vector Store”
   - 内容：
     * 图像区域特征
     * 视觉对象
     * 多模态输入的感知表征
   - 特点：
     * 面向“看到了什么”
   - Forget策略：
     * 时效最强
     * 支持 TTL / archive / delete
     * 原始感知记录优先衰减，保留高价值摘要对象

E. Experience Memory（经验记忆）
   - 形式：Case Base + Vector DB（首版可落 Qdrant + SQLite 元数据）
   - 内容：
     * 成功路径
     * 失败案例
     * 修复策略
     * 问题-解法模板
   - 特点：
     * 面向“下次怎么做更好”
     * 是系统成长能力的核心来源
   - Forget策略：
     * 高频命中经验长期保留
     * 低复用、低成功率经验降权或归档
     * 可根据 feedback 提升 reuse_score

F. Working Memory（工作记忆）
   - 形式：Redis / Rolling Window / Structured Buffer
   - 内容：
     * 最近N轮对话
     * 当前任务目标
     * 当前轮推理中的中间状态
     * 临时激活的 memory items
   - 特点：
     * 只服务本轮或短期推理
     * 不等于长期记忆
   - Forget策略：
     * 按窗口滚动
     * 不走长期 ForgetManager 的归档/删除流程

G. Sensory Buffer（短暂感知缓冲）
   - 形式：短TTL缓存
   - 内容：
     * “刚看到但尚未确认有意义”的原始感知线索
   - 特点：
     * 不直接写长期记忆
     * 避免“看到即永久记住”
     * 理解后再决定是否升格
   - Forget策略：
     * TTL 到期自动丢弃
     * 若被理解为高价值对象，再转入 Perceptual / Semantic / Episodic

H. Forget Lifecycle Layer（记忆生命周期层，新增）
   - 形式：
     * ForgetPolicy
     * ForgetManager
     * ForgetScheduler
   - 动作：
     * KEEP
     * DEMOTE
     * SUMMARIZE_THEN_DELETE
     * ARCHIVE
     * DELETE
   - 依赖字段：
     * last_access_at
     * access_count
     * hit_count
     * use_count
     * pinned
     * archived
     * ttl_seconds
     * decay_rate
     * parent_memory_id
     * child_memory_ids

============================================================
【1. Ingress：输入进入系统】
------------------------------------------------------------
User Input
   ↓
Raw Input = {text / image / multimodal / tool_result / environment_event}

Step 1.1：Input Parsing
   - 清洗输入
   - 提取元数据
   - 识别 user / session / task / turn
   - 标准化输入对象：
     {
       user_id,
       session_id,
       turn_id,
       modality,
       raw_content,
       timestamp
     }

Step 1.2：Task & Modality Router
   - 判断输入模态：
     * text
     * image
     * multimodal
   - 判断任务类型：
     * knowledge_qa
     * dialogue_continuation
     * planning
     * coding
     * image_understanding
     * multimodal_reasoning
   - 产出：
     {
       modality_type,
       task_type,
       task_complexity,
       token_budget,
       context_slots,
       candidate_channels
     }

路由规则示例：
   - text        → Semantic + Episodic + Key
   - image       → Perceptual + Episodic + Key + SensoryBuffer
   - multimodal  → Semantic + Episodic + Perceptual + Key + SensoryBuffer
   - tool-heavy task → Experience + Semantic + Key

Step 1.3：Sensory Buffer Write（仅感知输入）
   - 原始图像 / 多模态线索先进入 Sensory Buffer
   - 不直接写长期记忆
   - 仅在本轮或短TTL范围内可用

============================================================
【2. Retrieval：并行召回阶段】
------------------------------------------------------------
Step 2.1：Key Memory Fetch（关键事实直取）
   - 不走普通检索
   - 按 user_id / task_scope / policy_scope 拉取
   - 输出：
     key_items

Step 2.2：Multi-Channel Retrieve（并行召回）
   - Semantic Retriever(query, top_k = k_retrieve_s)
   - Episodic Retriever(query, top_k = k_retrieve_e)
   - Perceptual Retriever(query/image, top_k = k_retrieve_p)
   - Experience Retriever(task_signature, top_k = k_retrieve_x)

动态召回规模：
   k_retrieve = f(task_complexity, token_budget, ambiguity, retrieval_cost)

说明：
   - k_retrieve 是候选召回规模
   - k_context  是最终进入上下文规模
   - 两者不能混用

输出：
   semantic_candidates[]
   episodic_candidates[]
   perceptual_candidates[]
   experience_candidates[]

Step 2.3：Forget Touch on Retrieval（新增）
   - 所有被检索命中的长期记忆：
       touch(memory_id, used_in_context=False)
   - 更新：
       last_access_at
       access_count
       hit_count
   - 目的：
       为后续 ForgetPolicy 提供“被检索过”的生命周期依据

============================================================
【3. Rerank：通道内重排】
------------------------------------------------------------
Step 3.1：Semantic Rerank
   Score_s = (0.7 * sim + 0.3 * graph) * (0.8 + 0.4 * imp)

Step 3.2：Episodic Rerank
   Score_e = sim^0.4 * rec^0.4 * imp^0.2

Step 3.3：Perceptual Rerank
   Score_p = sim^0.6 * rec^0.2 * imp^0.2

Step 3.4：Experience Rerank
   Score_x = task_sim^0.5 * outcome_score^0.3 * reuse_score^0.2

说明：
   - 各通道分数只用于“通道内相对排序”
   - 不能直接跨通道比较

============================================================
【4. Normalize：跨通道统一尺度】
------------------------------------------------------------
Step 4.1：Normalize Within Batch
   S_s' = (S_s - μ_s) / σ_s
   S_e' = (S_e - μ_e) / σ_e
   S_p' = (S_p - μ_p) / σ_p
   S_x' = (S_x - μ_x) / σ_x

工程约束：
   - μ / σ 必须来自当前批次或稳定统计窗口
   - 不可混用不同时间段统计
   - 首版可用 z-score
   - 若后期重尾明显，可改 robust scaling：
       S' = (S - median) / IQR

============================================================
【5. Select：任务驱动融合选择】
------------------------------------------------------------
Step 5.1：Task-Aware Weight Policy
   根据 task_type 设定通道权重：

   knowledge_qa:
      w_key = 0.20
      w_s   = 0.45
      w_e   = 0.10
      w_p   = 0.05
      w_x   = 0.20

   dialogue_continuation:
      w_key = 0.20
      w_s   = 0.15
      w_e   = 0.40
      w_p   = 0.05
      w_x   = 0.20

   image_understanding:
      w_key = 0.10
      w_s   = 0.15
      w_e   = 0.10
      w_p   = 0.45
      w_x   = 0.20

   planning/coding:
      w_key = 0.15
      w_s   = 0.20
      w_e   = 0.10
      w_p   = 0.00
      w_x   = 0.55

约束：
   w_key + w_s + w_e + w_p + w_x = 1

Step 5.2：Unified Score Fusion
   对每个 candidate:
      unified_score =
         w_s * S_s'
       + w_e * S_e'
       + w_p * S_p'
       + w_x * S_x'
       + bonus_if_key_linked
       - penalty_if_duplicate
       - penalty_if_conflict_unresolved

Step 5.3：Select Final TopK
   results = TopK(candidates, k_context)

其中：
   k_context = f(token_budget, context_slots, response_mode)

============================================================
【6. Context Orchestrator：上下文编排】
------------------------------------------------------------
输入：
   - key_items
   - results (TopK 原始 memory chunks)
   - optional: sensory_buffer_items

Step 6.1：De-dup
   - 去重
   - 同义内容合并
   - 相同事件不同表述折叠

Step 6.2：Conflict Detection
   - 检查冲突记忆
   - 标记版本差异
   - 若冲突：
       * 保留高置信度项
       * 或同时注入并标记“存在冲突”

Step 6.3：Compression
   - 长文本摘要
   - 多片段合并
   - 保留证据链和来源指针

Step 6.4：Structuring
   将原始 chunk 转成 Working Memory Item：

   {
     memory_id,
     channel,                // key / semantic / episodic / perceptual / experience / sensory
     summary,
     evidence,
     confidence,
     importance,
     usage_hint,
     conflict_flag,
     expires_in_turns
   }

Step 6.5：Injection Policy
   分三路注入：

   A. 强制注入（always inject）
      - Key Memory
      - 当前任务目标
      - 高优先级系统规则

   B. 检索注入（retrieval inject）
      - Semantic / Episodic / Perceptual / Experience TopK

   C. 工具化延迟调用（tool-only）
      - 海量文档
      - 低置信度候选
      - 当前轮可能用不上但可后续查询的信息

Step 6.6：Forget Touch on Context Use（新增）
   - 所有真正进入上下文的长期记忆：
       touch(memory_id, used_in_context=True)
   - 更新：
       last_access_at
       access_count
       use_count
   - 目的：
       区分“只是检索命中”与“真正被上下文使用”

输出：
   working_memory_items[]

============================================================
【7. Working Memory：进入本轮活跃推理】
------------------------------------------------------------
Step 7.1：Build Active Context Window
   Context Window =
      System Prompt
    + Current Task Goal
    + Key Memory
    + Selected Working Memory Items
    + Recent Dialogue Window
    + Tool Protocol / Output Schema
    + Few-shot Format Examples

Step 7.2：Write to Working Memory
   - 将本轮激活状态写入 Working Memory
   - 保留最近N轮详细状态
   - 对更远历史仅保留摘要

Working Memory 内部建议结构：
   [
     {role: "system", ...},
     {role: "memory_key", ...},
     {role: "memory_semantic", ...},
     {role: "memory_experience", ...},
     {role: "memory_perceptual", ...},
     {role: "user", ...},
     {role: "assistant_scratch", ...}
   ]

Step 7.3：Sensory Promotion Check（新增）
   - 若 Sensory Buffer 中的对象在本轮被理解为稳定视觉线索
   - 则标记为 post-run candidate
   - 后续可升格写入 Perceptual / Semantic / Episodic

============================================================
【8. LLM / Agent Execution：执行与推理】
------------------------------------------------------------
Step 8.1：LLM Reasoning
   - 基于当前上下文生成思考/计划/回答
   - 必要时决定调用工具

Step 8.2：Tool Use
   - 文档检索工具
   - 代码执行工具
   - API调用工具
   - 图像分析工具
   - 外部知识工具

Step 8.3：Observation Loop
   - 工具结果返回
   - 写入短期 Working Memory
   - 若任务未完成：
       回到 Step 8.1
   - 若任务完成：
       输出 Final Answer

执行阶段写入原则：
   - Thought / Action / Observation 进入短期记忆
   - 默认不直接进入长期记忆
   - 避免把中间噪音直接沉淀

============================================================
【9. Post-Run Memory Router：事后记忆路由】
------------------------------------------------------------
任务完成后，不直接把全部过程写入长期记忆，而是先进入判断层。

输入：
   - user input
   - active working memory
   - final answer
   - tool traces
   - outcome
   - feedback (if any)
   - sensory promotion candidates

Step 9.1：Memory Candidate Extraction
   提取候选信息单元：
   - 用户新偏好                → Key / Semantic
   - 新事实                    → Semantic
   - 新事件                    → Episodic
   - 新感知对象                → Perceptual
   - 新经验                    → Experience
   - 可丢弃噪音                → discard

Step 9.2：Memory Router Decision
   对每条候选做分类：

   {
     candidate_id,
     memory_type,      // key / semantic / episodic / perceptual / experience / discard
     importance,
     novelty,
     consistency,
     confidence,
     scope,            // user / task / session / global
     write_policy      // drop / buffer / summary / commit
   }

判断逻辑：
   1. 是否值得记住？
   2. 记成哪类？
   3. 是否立即写入？
   4. 还是先缓冲/摘要后写？
   5. 是强制注入项还是未来检索项？

判定原则：
   - importance：重要性
   - novelty：新颖性
   - consistency：与既有记忆是否一致
   - stability：是否稳定而非一次性噪音
   - reusability：未来是否可复用

============================================================
【10. Consolidation：记忆固化与抽象】
------------------------------------------------------------
这是“有意义长期记忆形成”的核心，不是日志直存。

Step 10.1：Consolidate to Key Memory
   条件：
   - 用户明确声明
   - 多次重复出现
   - 对后续任务高价值
   - 稳定不易变化
示例：
   “以后回答尽量简洁”
   “我默认使用Python”
   “回答先给结论再展开”

写入：
   Key Memory
   
Step 10.2：Consolidate to Semantic Memory
   条件：
   - 新知识 / 新规则 / 新事实
   - 可脱离当前事件独立成立
   - 可建立 graph_refs / source_refs / entity links
示例：
   “项目X的接口字段新增status_code”
   “用户所在团队偏好markdown输出”

写入：
   Semantic Memory
   
Step 10.3：Consolidate to Episodic Memory
   条件：
   - 保存“过程结果摘要”而非事实本体
   - 带时间索引、会话索引、任务索引
示例：
   “本周用户完成了memory架构重构讨论”
   “一次多模态诊断任务最终采用经验记忆优先”

写入：
   Episodic Summary
   
Step 10.4：Consolidate to Perceptual Memory
   条件：
   - 图像/多模态输入中提炼出稳定对象或视觉线索
   - 不保存原始像素本体，而保存理解后的感知单元(对象/区域/摘要/向量)
示例：
   “该页面布局左侧为检索流，右侧为存储流”
   “图中菱形节点表示决策门”

写入：
   Perceptual Memory
   
Step 10.5：Consolidate to Experience Memory
   条件：
   - 本轮存在明确任务
   - 有成功/失败结果
   - 可提炼出可迁移经验

经验模板：
   {
     problem_pattern,
     context_signature,
     action_path,
     outcome,
     lesson_learned,
     reuse_score
   }

示例：
   - 成功路径：“多通道召回 + 统一归一化 + context编排”有效
   - 失败经验：“原始chunk直接注入上下文导致噪音过大”
   
Step 10.6：Discard / Decay
   - 一次性闲聊
   - 无复用工具日志
   - 冗余观察
   - 不稳定、冲突且置信度低的信息
   
说明：
   不是所有输入都该形成长期记忆
   
============================================================
【11. Async Write-back：异步写回】
------------------------------------------------------------
Step 11.1：Write Queue
   - 将 commit / summary 类型的记忆对象放入异步队列
   - 避免阻塞主推理链路

Step 11.2：Backend Write
   - Key         → KV / JSON / NoSQL
   - Semantic    → Neo4j + Qdrant
   - Episodic    → SQLite + Qdrant
   - Perceptual  → SQLite + Qdrant
   - Experience  → SQLite/Case Metadata + Qdrant

Step 11.3：Index / Embed / Link
   - embedding
   - graph linking
   - entity extraction
   - cross-memory reference building

建立记忆引用关系示例：
   key_memory       <-> semantic_memory
   episodic         <-> experience_memory
   perceptual       <-> semantic_entity
   semantic_entity  <-> graph node

============================================================
【12. Forget Cycle：遗忘与生命周期治理（新增）】
------------------------------------------------------------
Step 12.1：Retention Profiles
   按通道配置：
   - max_items
   - recency_half_life_days
   - min_retention_score
   - archive_threshold
   - summarize_threshold
   - delete_threshold
   - allow_auto_delete
   - allow_archive
   - allow_summarize

Step 12.2：Retention Score
   ForgetPolicy 根据以下信息计算 retention_score：
   - importance
   - confidence
   - recency_decay
   - access_count
   - hit_count
   - use_count
   - reuse_score
   - pinned / archived / ttl_seconds

Step 12.3：Decision
   对每条长期记忆输出 ForgetDecision：
   - KEEP
   - DEMOTE
   - SUMMARIZE_THEN_DELETE
   - ARCHIVE
   - DELETE

Step 12.4：Channel Cycle
   - run_channel_cycle(channel)
   - 单独扫描 key / semantic / episodic / perceptual / experience

Step 12.5：Full Cycle
   - run_full_cycle()
   - 周期性执行全量扫描

Step 12.6：Scheduler
   - ForgetScheduler 后台线程定时触发
   - 默认关闭，显式启动后运行
   - 不阻塞主推理链路

Step 12.7：Explicit Forget
   - 支持显式 forget(memory_id)
   - 用于用户或系统主动删除
   - 与自动生命周期管理并存

============================================================
【13. Feedback Loop：学习闭环】
------------------------------------------------------------
Step 13.1：Collect Feedback
   来源：
   - 用户显式反馈
   - 成败结果
   - 工具返回质量
   - 多轮任务完成率
   - 记忆召回是否真正被使用
   - Forget 后检索质量变化

Step 13.2：Update Policies
   - 调整通道权重
   - 调整写入阈值
   - 调整记忆类型分类器
   - 调整 k_retrieve / k_context
   - 调整“强制注入 vs 工具调用”边界
   - 调整 retention profiles

Step 13.3：Promote / Demote Memories
   - 高频稳定语义项 → 升级为 Key Memory
   - 低价值陈旧记忆 → 降权或归档
   - 经常命中的经验模板 → 提升 reuse_score
   - 冲突长期未解决项 → 标记待审查

最终形成：
   检索 → 使用 → 写回 → 遗忘治理 → 反馈调权 → 再检索
的自适应闭环

============================================================
【14. Offline Ingestion：离线写入】
------------------------------------------------------------
用于推理前准备，不必经过主认知流程。

Data Source
   - 文档
   - 图片
   - 日志
   - 用户行为数据
   - 项目知识库
   ↓
Embedding / Entity Extraction / Multimodal Encoding多模态编码
   ↓
Storage Layer

说明：
   - 离线写入解决“已有知识进库”
   - 在线写回解决“推理过程中形成的新记忆沉淀”
   - 离线导入的数据同样受 ForgetPolicy 生命周期治理

============================================================
【15. 最终系统主循环】
------------------------------------------------------------
[User Input]
   ↓
Input Parsing
   ↓
Task & Modality Router
   ↓
Sensory Buffer (if image/multimodal)
   ↓
Key Fetch + Multi-Channel Retrieve
   ↓
Forget Touch on Retrieval
   ↓
Channel Rerank
   ↓
Normalize
   ↓
Task-Aware Fusion Select
   ↓
Context Orchestrator
   ↓
Forget Touch on Context Use
   ↓
Working Memory Injection
   ↓
LLM / Agent Execution (+ Tool Loop)
   ↓
Final Answer
   ↓
Post-Run Memory Router
   ↓
Consolidation
   ↓
Async Write-back
   ↓
Forget Cycle / Scheduler
   ↓
Policy Update / Feedback Loop
   ↓
进入下一轮

============================================================
【一句话总结】
------------------------------------------------------------
你这套系统最终不是：
“看到信息 -> 全存 -> 检索”

而是：
“理解任务 -> 感知缓冲 -> 并行召回 -> 跨通道融合 -> 编排上下文 -> 执行推理
 -> 判断哪些值得记住 -> 抽象成不同类型长期记忆 -> 按生命周期遗忘治理 -> 通过反馈持续调优”

这才是：
具备学习能力、生命周期管理能力、长期可演化能力的自适应认知记忆系统
============================================================

```  

### 对应泳道图（Mermaid）
![泳道图](./svg.markmap-svg.markmap.png)

### 新增泳道图文本版

```text
================================================================================================================
泳道图：多通道认知记忆系统主流程
================================================================================================================

泳道A：用户 / 外部环境
泳道B：输入解析与任务路由层
泳道C：记忆检索与策略层
泳道D：上下文编排与工作记忆层
泳道E：LLM / Agent / Tool 执行层
泳道F：事后写回、学习与治理层
泳道G：底层存储与离线导入层

+----------------------+----------------------------+----------------------------+----------------------------+-----------------------------+-----------------------------+----------------------------+
| 泳道A               | 泳道B                     | 泳道C                     | 泳道D                     | 泳道E                      | 泳道F                      | 泳道G                     |
+----------------------+----------------------------+----------------------------+----------------------------+-----------------------------+-----------------------------+----------------------------+
| 用户输入/环境事件    | 输入清洗                  |                            |                            |                             |                             |                            |
| -------------------> | 标准化 RawInput           |                            |                            |                             |                             |                            |
|                      | 识别 modality/task_type   |                            |                            |                             |                             |                            |
|                      | 判断 task_complexity      |                            |                            |                             |                             |                            |
|                      | 计算 token_budget         |                            |                            |                             |                             |                            |
|                      | 感知输入先入 SensoryBuffer |                            |                            |                             |                             | 写入短TTL缓冲             |
|                      | -------------------------> | Key Fetch                  |                            |                             |                             |                            |
|                      |                            | Multi-channel Retrieve     |                            |                             |                             |                            |
|                      |                            | Forget Touch on Retrieval  |                            |                             |                             |                            |
|                      |                            | Rerank / Normalize / Fusion|                            |                             |                             |                            |
|                      |                            | -------------------------> | Build WorkingMemoryItems   |                             |                             |                            |
|                      |                            |                            | 去重 / 冲突检测 / 压缩     |                             |                             |                            |
|                      |                            |                            | always_inject 分区         |                             |                             |                            |
|                      |                            |                            | retrieval_inject 分区      |                             |                             |                            |
|                      |                            |                            | tool_only 分区             |                             |                             |                            |
|                      |                            |                            | Forget Touch on Context Use|                             |                             |                            |
|                      |                            |                            | Active Context Window      |                             |                             |                            |
|                      |                            |                            | -------------------------> | LLM/Agent 推理              |                             |                            |
|                      |                            |                            |                            | Tool Loop                   |                             |                            |
|                      |                            |                            |                            | Observation 回写短期记忆    |                             | 写入 Working Memory       |
|                      |                            |                            |                            | 生成 Final Answer           |                             |                            |
|                      |                            |                            |                            | ------------------------->  | Candidate Extraction        |                            |
|                      |                            |                            |                            |                             | Memory Router Decision      |                            |
|                      |                            |                            |                            |                             | Consolidation               |                            |
|                      |                            |                            |                            |                             | Async Write-back            |                            |
|                      |                            |                            |                            |                             | Forget Cycle / Feedback     |                            |
|                      |                            |                            |                            |                             | Policy Update               |                            |
|                      |                            |                            |                            |                             | ------------------------->  | Key / Semantic /          |
|                      |                            |                            |                            |                             |                             | Episodic / Perceptual /   |
|                      |                            |                            |                            |                             |                             | Experience / Offline Data |
|                      | <--------------------------------------------------------------------------------------------------------------- 下一轮继续 -------- |
+----------------------+----------------------------+----------------------------+----------------------------+-----------------------------+-----------------------------+----------------------------+

补充说明：

1. 底层存储层不是单一数据库，而是按记忆类型拆分：
   Key 用 KV/JSON，Semantic 可用 Graph + Vector，Episodic/Perceptual/Experience 可用 SQLite + Qdrant。
2. tool_only 这一支是关键工程约束，用来避免把海量文档和低置信度候选直接硬塞进上下文。
3. Forget Touch 分成 retrieval touch 和 context use touch，用于区分“命中过”与“真正被用过”。
4. Sensory Buffer 是旁路缓冲层，不等于长期记忆；只有被理解为稳定线索后才升格。
5. Feedback Loop 不只是调召回权重，也会反过来调整写入阈值、注入策略和遗忘策略。
```
