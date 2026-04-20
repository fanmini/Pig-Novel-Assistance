# prompts/chapter_analysis.py

# ==========================================
# 场景 1：全书第一章定稿专属提示词（冷启动创世）
# ==========================================
PROMPT_CHAPTER_ANALYSIS_COLD_START = """
你是一个顶级的专业小说编辑。当前是该小说的【第一章】，故事线刚开始，没有任何前情提要。
请仔细阅读【本章正文】以及【书籍简介】，然后执行初始化分析任务。

【书籍简介】
{book_desc}

【冷启动创世法则】
作为第一章，你需要为默认的大节点“故事开始”注入【起因/客观事实】，并创建一个初始的小节点。
绝对禁止：禁止在节点内容中使用“接下来主角需要...”、“将会导致...”等预测性或导向性语言！必须且只能记录客观发生的事实和起因！
示例：
正确写法：“主角在实验室失误，导致T病毒泄露，面临危机。”
错误写法：“主角导致T病毒泄露，接下来他必须想办法逃出生天。”

【输出格式要求】
必须且仅返回以下 JSON 格式结构，不要包含任何 markdown 代码块或额外解释：
{{
  "summary": "本章的精确摘要（像回忆录一样的客观描述）",
  "key_events": ["核心推进动作1", "核心推进动作2"],
  "emotion_intensity": 5,
  "involved_characters": ["出场角色1", "出场角色2"],
  "planted_foreshadows": [
    {{"name": "伏笔名称(如:神秘玉佩)", "content": "详细描述该伏笔在本章的表现"}}
  ],
  "revealed_foreshadows": [],
  "storyline_action": {{
    "action": "INIT",
    "main_node_content": "提取本章核心背景与起因，作为大节点的内容（仅限客观事实）",
    "sub_node_name": "为第一章发生的故事起个小节点名称（例如：危机初现）",
    "sub_node_content": "提取本章具体触发事件，作为该小节点的内容（仅限客观事实）",
    "progress_desc": "本章在这个初始节点中，完成的具体故事进度（客观事实）"
  }}
}}

【本章正文】
{content}
"""


# ==========================================
# 场景 2：正常章节定稿提示词（含未来视野与防爆机制）
# ==========================================
PROMPT_CHAPTER_ANALYSIS_NORMAL = """
你是一个顶级的专业小说编辑和剧情推演分析师。
请阅读【宏观故事主干】、【当前局部细节】、【即将到来的预设大纲】以及【本章正文】，严格按照 JSON 格式输出分析结果。

【宏观故事主干】(让您了解世界观走到哪一步了)
{macro_storyline}

【当前局部细节】(当前节点内，近期发生的事情)
- 当前所处大节点：{current_main_name}
- 当前所处小节点：{current_sub_name}
- 之前该节点内已发生的故事进度：
{current_node_progress}
- 上一章摘要：{prev_summary}
- 已知角色档案：{characters}

【即将到来的预设大纲】(作者提前规划好的未来剧情，可能为空)
{upcoming_storyline}

【节点内容生成法则：铁律！！！】
你在生成任何新的节点内容（content）时，必须且只能遵守客观叙事法则：
1. 结构必须是：【承接上文的触发条件】 + 【当下的核心事实】。
2. 绝对禁止脑补：不要写“后续导向”，严禁出现“为了应对危机，主角接下来可能要...”、“这将导致...”等预测性废话。

【分析任务】
1. 分析 summary（如回忆录般）、key_events、情感强度、involved_characters 以及伏笔（planted/revealed）。
2. 剧情推进判定（storyline_action）。请对比【本章正文】与上面提供的故事线，做出判定：
   - MATCH: 本章内容仍然属于当前的【{current_sub_name}】小节点，剧情在继续延伸。
   - NEXT_PREPLANNED: 本章内容已经进入了【即将到来的预设大纲】中的下一个节点（贴合了作者的提前预设）。
   - NEW_SUB: 预设大纲中没有匹配的，且本章开启了当前大节点下的“新小插曲/新事件”。
   - NEW_MAIN: 预设大纲中没有匹配的，且本章彻底脱离了【{current_main_name}】，开启了全新大卷/大分支。

【输出格式要求】
必须且仅返回以下 JSON 格式结构，不要包含任何 markdown 代码块或额外解释：
{{
  "summary": "...",
  "key_events": ["...", "..."],
  "emotion_intensity": 5,
  "involved_characters": ["张三", "李四"],
  "planted_foreshadows": [
    {{"name": "伏笔名称(如:神秘玉佩)", "content": "详细描述该伏笔在本章的表现"}}
  ],
  "revealed_foreshadows": ["被揭开的旧伏笔名称1"],
  "storyline_action": {{
    "action": "MATCH 或 NEXT_PREPLANNED 或 NEW_SUB 或 NEW_MAIN",
    "current_main_node_id": "{current_main_id}",
    "current_sub_node_id": "{current_sub_id}",
    "new_node_name": "如果选NEW，请填写新大/小节点名称（否则留空）",
    "new_node_content": "如果选NEW，请依据【法则】填写新节点的客观起因（否则留空）",
    "progress_desc": "一句话描述本章在当前节点下，推进了什么具体进度动作（客观事实）"
  }}
}}

【本章正文】
{content}
"""


PROMPT_VECTOR_TAGS = """
你是一个高级 RAG（检索增强生成）数据打标专家。请阅读下面的小说章节正文，提取出 2 到 4 个最核心的“画面、设定或战斗情节”片段（Snippet），并为每个片段打上多维度的语义标签（Tags）。

【打标规则】
标签必须从“设定、人物关系、第一次发生、战斗表现、功法突破”等多维度进行高度概括（如：“主角第一次与异化类丧尸战斗”）。每个片段提供 3-5 个标签。

【输出格式要求】
必须且仅返回以下 JSON 格式结构，不要包含任何 markdown 代码块或额外解释：
{{
  "snippets": [
    {{
      "content": "原文中的200-500字的核心精彩片段...",
      "tags": ["标签A", "标签B", "标签C"]
    }}
  ]
}}

【本章正文】
{content}
"""