# 文件名: main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# 1. 初始化 FastAPI 应用
app = FastAPI(title="SnapDownloader MVP Backend")

# 2. 开启 CORS 跨域配置（允许任何地方的前端进行访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 允许所有网站域名访问
    allow_credentials=True,
    allow_methods=["*"],          # 允许所有请求方法（GET, POST 等）
    allow_headers=["*"],          # 允许所有请求头
)

# 3. 健康检查接口（用来测试后端是否正常在线）
@app.get("/")
@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "message": "SnapDownloader 后端服务已成功启动！"}

# 4. 智能提取接口（接收前端链接，返回指定的假数据）
@app.post("/api/v1/extract")
async def extract_stream(request: Request):
    # 自动读取前端传过来的原始文本链接
    raw_body = await request.body()
    url_input = raw_body.decode("utf-8")
    
    # 在后端控制台打印出来，方便你观察是否接收成功
    print(f"========================================")
    print(f"🚀 成功收到前端发送的解析链接: {url_input}")
    print(f"========================================")
    
    # 直接返回完全符合你前端数据结构的 JSON 假数据
    return {
        "type": "video",
        "title": "测试视频：这是一个超棒的无水印原流视频",
        "size": "15.4 MB",
        "cover": "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500",
        "actions": [
            { "type": "primary", "label": "🟢 高速无损下载" }
        ]
    }