# 文件名: main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

# 1. 初始化 FastAPI 应用
app = FastAPI(title="SnapDownloader Production Backend")

# 2. 开启全量 CORS 跨域配置，允许任何地方的前端进行跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 允许所有域名跨域访问
    allow_credentials=True,
    allow_methods=["*"],          # 允许所有请求方法 (POST, GET 等)
    allow_headers=["*"],          # 允许所有请求头
)

# 3. 健康检查接口（方便 Render 监控检查服务状态）
@app.get("/")
@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "message": "视频流解析后端服务正在运行中..."}

# 4. 真实原流提取接口
@app.post("/api/v1/extract")
async def extract_stream(request: Request):
    try:
        # 核心逻辑：直接读取前端发送的裸文本（text/plain）请求体
        raw_body = await request.body()
        url_input = raw_body.decode("utf-8").strip()
        
        # 控制台打印记录，方便调试查看
        print(f"========================================")
        print(f"📡 收到前端裸文本解析请求: {url_input}")
        print(f"========================================")
        
        if not url_input:
            raise HTTPException(status_code=400, detail="输入的视频网址不能为空")
            
        # 配置 yt-dlp 核心参数
        ydl_opts = {
            'quiet': True,            # 禁止打印多余的运行时调试日志
            'no_warnings': True,      # 忽略非致命警告
            'skip_download': True,    # 核心：只抓取元数据，绝不下载视频到服务器本地，保护硬盘
            'extract_flat': False,    # 深度提取流媒体真实的直链地址
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 开始调用库进行真实网页嗅探与解析
            info = ydl.extract_info(url_input, download=False)
            
            # 1. 提取真实视频标题
            title = info.get('title', '未命名原流视频')
            
            # 2. 提取最高清封面图网址
            cover = info.get('thumbnail')
            if not cover and info.get('thumbnails'):
                cover = info['thumbnails'][-1].get('url')  # 尝试获取列表中分辨率最高的封面
            if not cover:
                cover = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500"  # 兜底默认图
                
            # 3. 提取真实的视频原流直链下载链接
            video_url = info.get('url')
            if not video_url and info.get('formats'):
                # 如果外层没有直接提供 url，则去 formats 格式列表中筛选出有效的直链
                valid_formats = [f for f in info['formats'] if f.get('url')]
                if valid_formats:
                    # 通常列表最后的格式清晰度与完整度最高
                    video_url = valid_formats[-1].get('url')
                    
            if not video_url:
                raise Exception("无法从该页面中提取出有效的原音频/视频无水印直链地址")
                
            # 4. 计算或预估真实文件大小
            filesize = info.get('filesize') or info.get('filesize_approx')
            if filesize:
                size_str = f"{filesize / (1024 * 1024):.1f} MB"
            else:
                size_str = "高清原流"
                
            # 5. 严格返回完全适配前端渲染组件的 JSON 数据结构
            return {
                "type": "video",
                "title": title,
                "size": size_str,
                "cover": cover,
                "actions": [
                    { "type": "primary", "label": "🟢 高速无损下载", "url": video_url }
                ]
            }
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 解析服务崩溃，异常原因: {error_msg}")
        # 发生错误时拦截并返回 500 状态码，透传错误信息，完美触发前端的异常弹窗拦截组件
        raise HTTPException(status_code=500, detail=f"解析失败: {error_msg}")