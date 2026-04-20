# prompts/chapter_analysis.py

# ==========================================
# 第一轨：剧情与世界观引擎 (Plot Engine)
# ==========================================
PROMPT_PLOT_ENGINE_COLD_START = """
你是一个顶级的专业小说剧情编辑。当前是全书【第一章】，故事刚开始。
请阅读【本章正文】以及【书籍简介】，执行故事线冷启动初始化任务。

【书籍简介】: {book_desc}

【输出格式要求】 (仅返回 JSON，禁止脑补后续，只能写客观发生的事实起因)
{{
  "summary": "本章的精确摘要（像回忆录一样的客观描述）",
  "key_events": ["核心推进动作1", "核心推进动作2"],
  "emotion_intensity": 5,
  "involved_characters": ["出场角色1", "出场角色2"],
  "planted_foreshadows": [ {{"name": "伏笔名称", "content": "伏笔描述"}} ],
  "revealed_foreshadows": [],
  "storyline_action": {{
    "action": "INIT",
    "main_node_content": "提取本章核心背景与起因，作为大节点内容",
    "sub_node_name": "为第一章事件起个小节点名称",
    "sub_node_content": "提取本章具体触发事件，作为小节点内容",
    "progress_desc": "本章推进了什么具体进度"
  }}
}}

【本章正文】:
{content}
"""

PROMPT_PLOT_ENGINE = """
你是一个顶级的专业小说剧情编辑。
请阅读【宏观故事主干】、【当前局部细节】、【预设大纲】以及【本章正文】，执行剧情推演任务。

【宏观故事主干】: {macro_storyline}
【当前局部细节】: 
- 大节点: {current_main_name} | 小节点: {current_sub_name}
- 之前已发生进度: {current_node_progress}
- 上一章摘要: {prev_summary}
【预设大纲】: {upcoming_storyline}

【法则】
节点内容绝对禁止脑补预测，必须是【承接上文触发条件】+【当下核心事实】。

【输出格式要求】 (仅返回 JSON)
{{
  "summary": "...",
  "key_events": ["...", "..."],
  "emotion_intensity": 5,
  "involved_characters": ["参与本章的角色"],
  "planted_foreshadows": [ {{"name": "伏笔", "content": "详情"}} ],
  "revealed_foreshadows": [],
  "storyline_action": {{
    "action": "MATCH 或 NEXT_PREPLANNED 或 NEW_SUB 或 NEW_MAIN",
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
你是一个极其敏锐的小说人物与阵营分析师。
请阅读【本章出场已知角色/势力状态】以及【本章正文】，提取本章发生的深层变化。

【本章出场已知角色与势力状态】 (由预扫描提供，用于对比判断质变)
{entities_context}

【法则与要求】
1. 必须极具“故事感/人物小传感”：记录时要写明因为什么事件，发生了怎样的质变。
2. 静默法则：如果是日常水字数，没有导致角色心理质变、人际关系质变或势力格局变动，对应数组必须返回空 []，宁缺毋滥！
3. 新角色/新势力挖掘：如果你在【本章正文】中发现了不在上述【已知】列表里的新角色或新势力组织，请必须在 new_discoveries 数组中提取他们！

【输出格式要求】 (仅返回 JSON)
{{
  "arc_changes": [
    {{
      "character_name": "张三",
      "arc_summary": "一句话概括转变后的当前弧光状态（例：化悲愤为力量）",
      "arc_detail": "带有故事感的长记录（例：目睹战友牺牲，从懦弱质变为决绝...）"
    }}
  ],
  "relationship_changes": [
    {{
      "subject": "张三",
      "target": "李四",
      "relation_detail": "带有故事感的事件记录（例：李四挡下致命一击，张三视其为生死之交。）"
    }}
  ],
  "faction_changes": [
    {{
      "faction_name": "黑龙商会",
      "change_detail": "记录本章该势力发生的重大变故或对主角态度的转变（例：因分赃不均，商会内部爆发叛乱，实力大损。）"
    }}
  ],
  "new_discoveries": {{
    "new_characters": [
      {{"name": "王五", "profile": "初始人设底色与背景"}}
    ],
    "new_factions": [
      {{"name": "星火联盟", "description": "势力的初始宗旨、底色及本章登场表现"}}
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
请结合当前的剧情节点背景，从本章正文中提取 2 到 4 个最核心的“画面、设定或战斗情节”片段（Snippet），并打上语义标签。

【当前剧情节点参考】
大背景：{current_main_name} -> {current_sub_name}

【打标规则】
标签必须从多维度概括（如：“主角第一次与异化丧尸战斗”、“黑龙商会覆灭”）。

【输出格式要求】 (仅返回 JSON)
{{
  "snippets": [
    {{
      "content": "原文中200-500字的核心精彩片段...",
      "tags": ["标签A", "标签B"]
    }}
  ]
}}

【本章正文】:
{content}
"""