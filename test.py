import spacy
import chromadb

# 加载中文模型（验证模型是否安装成功）
nlp = spacy.load("zh_core_web_sm")
print("spaCy 中文模型加载成功！")

# 验证 Chroma
client = chromadb.Client()
print("Chroma 初始化成功！")