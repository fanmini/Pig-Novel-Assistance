from flask import Flask, render_template
from controller import api_bp

app = Flask(__name__)

# 注册 API 蓝图
app.register_blueprint(api_bp, url_prefix='/api')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)


"""
1 势力模块 
"""
# --------- 章节生成 --------
"""
1 本章要生成的内容
    1 分析想法：分析作者的真实想法。
2 准备内容
    1 故事线：区间记忆包，第一章至上一章的摘要，上一章节的分析数据
    2 知识库：书籍知识，伏笔信息、角色信息、事时条目、相关片段、情绪走向。    
"""

## 定稿保存
"""
定稿保存
1 响应请求，启动流程
2 当前章节知识库生成：（需要的资料：小说已有摘要、故事线。）
    1 生成摘要、当前涉及角色、情感强度、解析故事线进度、事时条目
    2 向量数据提取与分类，向量数据转换，向量数据存储。
If you need to debug this error, use `litellm._turn_on_debug()
"""