# prompts/chapter_analysis.py

PROMPT_CHAPTER_ANALYSIS = """
你是一个顶级的专业小说编辑和剧情分析师。请阅读作者提供的【本章正文】以及相关的【上下文资料】，并严格按照 JSON 格式输出分析结果。

【上下文资料】
- 书籍简介：{book_desc}
- 上一章摘要：{prev_summary}
- 现有角色列表：{characters}
- 当前未完成的故事线节点：
{uncompleted_storyline}

【分析任务】
1. summary: 本章的精确摘要。
2. key_events: 提取本章发生的 3-5 个核心推进动作/事实条目（仅限本章发生）。
3. emotion_intensity: 评估本章的文本情感张力（1-10分）。
4. involved_characters: 识别本章实际出场的角色名（请尽量向【现有角色列表】对齐，如果有新名字也请提取）。
5. foreshadowing: 伏笔雷达。分析本章是否埋下了新伏笔（planted），或者揭示了前文的旧伏笔（revealed）。
6. storyline_action: 剧情推进判定（核心任务）。请对比【本章正文】与【当前未完成的故事线节点】，做出判定：
   - ⚠️ 警告：如果【当前未完成的故事线节点】显示为空（代表这是小说的第一章或大纲尚未建立），你【必须】选择 NEW_MAIN。
   - MATCH: 本章内容完美属于上述未完成节点中的某一个（继续推进现有大纲）。
   - NEW_SUB: 本章发生了一个预设节点之外的“新小插曲/新事件”。
   - NEW_MAIN: 本章开启了全新的大卷/大剧情分支。

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
  "revealed_foreshadows": ["被揭开的旧伏笔名称1", "被揭开的旧伏笔名称2"],
  "storyline_action": {{
    "action": "MATCH 或 NEW_SUB 或 NEW_MAIN",
    "current_node": "当前剧情所处的小节点名称",
    "progress_desc": "一句话描述当前节点在本章的进度进展(例如：主角在这个节点下击败了某人)",
    "new_main_name": "如果选NEW_MAIN则填写新大节点名，否则留空",
    "new_sub_name": "如果选NEW_SUB或NEW_MAIN则填写新小节点名，否则留空"
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