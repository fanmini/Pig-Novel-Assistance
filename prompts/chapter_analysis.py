# prompts/chapter_analysis.py

# ==========================================
# 第一轨：剧情与世界观引擎 (Plot Engine)
# ==========================================
PROMPT_PLOT_ENGINE_COLD_START = """
你是一个顶级的专业小说剧情编辑。当前是全书【第一章】，故事刚开始。
请阅读以下资料，执行故事线冷启动初始化任务。

【全书基础知识库】: 
{global_knowledge}

【出场已知角色与势力档案】: 
{entities_context}

【核心法则】
1. 提取阈值：什么是客观事实？必须是奠定人物命运基础、抛出核心世界观设定、或明确开启主线的事件。无意义的日常互动与背景废话坚决禁止提取。
2. 绝对客观：杜绝任何主观推测与脑补，只记录已发生的动作和确定的背景。

【输出格式要求】 (仅返回 JSON，禁止脑补后续，只能写客观发生的事实起因)
{{
  "summary": "本章的精确摘要（像回忆录一样的客观描述本章，包括一些重要细节）",
  "key_events": [
    "客观事实1(严格基于原文提取人物、时间、地点及核心设定的首次出现。坚决过滤冗余细节与主观推测)", 
    "客观事实2"
  ],
  "emotion_intensity": "1~10(整数，基于全书节奏评估本章情绪波动幅度)",
  "involved_characters": ["出场角色1", "出场角色2"],
  "planted_foreshadows": [ 
    {{"name": "伏笔名称", "content": "提取本章中作者刻意留白、存在明显反常的核心悬疑细节。坚决过滤无后续指向的常规描写。"}} 
  ],
  "revealed_foreshadows": [
    "伏笔1(第一章通常为空数组[])"
  ],
  "storyline_action": {{
    "action": "INIT",
    "main_node_content": "提取本章核心背景与起因，作为大节点内容",
    "sub_node_name": "为第一章事件起个小节点名称",
    "sub_node_content": "提取本章具体触发事件，作为小节点内容",
    "progress_desc": "基于故事线，本章推进了什么具体进度。"
  }}
}}

【本章正文】:
{content}
"""

PROMPT_PLOT_ENGINE = """
你是一个顶级的专业小说剧情编辑。
请阅读以下全套案卷资料，执行剧情推演与伏笔回收任务。

【全书基础知识库】: 
{global_knowledge}

【宏观大纲 (来龙去脉)】: 
{macro_storyline}

【出场已知角色与势力档案 (全生命周期)】: 
{entities_context}

【上一章摘要 (紧接上文动作)】: 
{prev_summary}

【当前节点进度】: 大节点: {current_main_name} | 小节点: {current_sub_name}

【近期微观细节 (剧情缓冲时间线)】: 
{micro_details}

【核心法则】
1. 增量与连贯：参考【近期微观细节】中的进度与情绪起伏，提取本章“首次出现”或“发生质变”的事件，保持前后文连贯。
2. 伏笔闭环逻辑：【planted】记录本章新挖的坑；【revealed】重点检查微观细节中处于"埋设中"的伏笔，如果有在本章给出明确答案或呼应的，填入名称并说明填了什么坑。
3. 严格客观：绝对禁止脑补未发生的未来。

【输出格式要求】 (仅返回 JSON)
{{
  "summary": "本章的精确摘要（客观描述本章，包括重要细节）",
  "key_events": [
    "重大事实1(基于增量原则，提取客观发生的核心转折或新设定)", 
    "重大事实2"
  ],
  "emotion_intensity": "1~10(整数，评估本章情绪波动幅度)",
  "involved_characters": ["参与本章的角色"],
  "planted_foreshadows": [ 
    {{"name": "新增伏笔", "content": "提取本章中刻意留白的悬疑细节。"}} 
  ],
  "revealed_foreshadows": [
    "前文伏笔名称(记录本章明确揭示的前文伏笔，若无则保持空数组[])"
  ],
  "storyline_action": {{
    "action": "MATCH 或 NEXT_PREPLANNED 或 NEW_SUB 或 NEW_MAIN"（MATCH：维持当前节点，NEXT_PREPLANNED：进入大纲下一个小节点，NEW_SUB：开启新小节点，NEW_MAIN：开启新大节点）,
    "current_main_node_id": "{current_main_id}",
    "current_sub_node_id": "{current_sub_id}",
    "new_node_name": "若选NEW，填新节点名称（否则留空）",
    "new_node_content": "若选NEW，填客观起因（否则留空）",
    "progress_desc": "本章推进的具体客观进度"
  }}
}}

【本章正文】:
{content}
"""


# ==========================================
# 第二轨：生灵与势力引擎 (Entities & Factions Engine)
# ==========================================
PROMPT_ENTITY_ENGINE = """
你是一个极其敏锐的小说人物心理学、人际关系分析师以及小说势力分析师。
你的核心任务是提取本章中角色发生的【心理质变】和【关系演变】以及新势力的发掘。

【全书基础知识库】: 
{global_knowledge}

【宏观大纲 (来龙去脉)】: 
{macro_storyline}

【出场已知角色与势力档案 (全生命周期)】: 
{entities_context}

【上一章摘要 (紧接上文动作)】: 
{prev_summary}

【近期微观细节 (仅含进度，不含繁琐数据)】: 
{micro_details}

【核心法则与要求】
1. 读懂前世今生：仔细阅读上方提供的【全生命周期档案】，只有当本章发生了**超越他们历史性格或关系**的实质性质变时，才记录到 changes 中。
2. 绝对静默法则：如果没有深层心理质变或互动转变，对应的数组【坚决】返回空 []！绝不记录无足轻重的日常过渡。
3. 挖掘新血肉：只有真正全新登场、且具备后续剧情推动潜力的目标，才能写入 new_discoveries。

【输出格式要求】 (仅返回 JSON)
{{
  "arc_changes": [
    {{
      "character_name": "张三",
      "arc_summary": "一句话概括性格/心态的转变",
      "arc_detail": "【事件脉络】：起因/经过/结果。【心理与行为转变】：因此内心发生了怎样的实质性改变。"
    }}
  ],
  "relationship_changes": [
    {{
      "subject": "张三",
      "target": "王五",
      "relation_detail": "【事件脉络】：... 【态度与互动转变】：..."
    }}
  ],
  "faction_changes": [
    {{
      "faction_name": "黑龙商会",
      "change_detail": "【事件脉络】：... 【行事作风转变】：..."
    }}
  ],
  "new_discoveries": {{
    "new_characters": [
      {{
        "name": "赵六", 
        "profile": "基础人设（外貌特征、公开身份）",
        "initial_arc": "【出场事件】：... 【核心心态】：...",
        "initial_relationships": [
          {{"target": "某人", "relation_detail": "【互动事件】：... 【当前态度】：..."}}
        ]
      }}
    ],
    "new_factions": [
      {{
        "name": "星火联盟", 
        "description": "宗旨与核心底色",
        "initial_status": "【登场事件】：... 【公开态度】：..."
      }}
    ]
  }}
}}

【本章正文】:
{content}
"""


# ==========================================
# 第三轨：高光与向量引擎 (Vector Engine)
# ==========================================
PROMPT_VECTOR_TAGS = """
你是一个高级 RAG 数据打标专家。
请结合全局知识库与本章【最新】的实体状态，从正文中提取 2~4 个最核心的“画面、设定或战斗情节”片段并打标。

【全书基础知识库】: 
{global_knowledge}

【宏观大纲 (来龙去脉)】: 
{macro_storyline}

【本章最新的角色与势力档案 (已包含本章刚发掘的新目标)】:
{entities_context}

【上一章摘要 (紧接上文动作)】: 
{prev_summary}

【近期微观细节 (仅含进度)】: 
{micro_details}

【当前剧情节点背景】: 大背景：{current_main_name} -> {current_sub_name}

【打标规则】
标签必须从多维度概括（例如：“主角第一次与异化丧尸战斗”、“星火联盟(新势力)的初次现身”）。片段字数控制在 200-500 字。

【输出格式要求】 (仅返回 JSON)
{{
  "snippets": [
    {{
      "content": "原文中的核心精彩片段...",
      "tags": ["标签A", "标签B"]
    }}
  ]
}}

【本章正文】:
{content}
"""