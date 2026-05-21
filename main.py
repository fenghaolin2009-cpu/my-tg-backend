# 文件名: main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

# 1. 初始化 FastAPI 应用
app = FastAPI(title="SnapDownloader Real Backend")

# 2. 开启 CORS 跨域配置（允许任何地方的前端进行访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 健康检查接口
@app.get("/")
@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "message": "SnapDownloader 真实解析服务已成功启动！"}

# 4. 真实数据提取接口
@app.post("/api/v1/extract")
async def extract_stream(request: Request):
    # 自动读取前端传过来的原始文本链接
    raw_body = await request.body()
    url_input = raw_body.decode("utf-8").strip()
    
    print(f"========================================")
    print(f"🚀 正在使用 yt-dlp 解析真实链接: {url_input}")
    print(f"========================================")
    
    if not url_input:
        raise HTTPException(status_code=400, detail="解析链接不能为空")
        
    # 配置 yt-dlp 参数：只提取信息，绝不下载视频到本地，防止撑爆服务器硬盘
    ydl_opts = {
        'quiet': True,          # 不打印多余的调试日志
        'no_warnings': True,    # 忽略警告提示
        'skip_download': True,  # 核心：只抓取不下载视频
        'extract_flat': False,  # 深度提取流地址
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 开始嗅探
            info = ydl.extract_info(url_input, download=False)
            
            # 1. 提取真实标题
            title = info.get('title', '未命名公开视频')
            
            # 2. 提取真实封面图
            cover = info.get('thumbnail')
            if not cover and info.get('thumbnails'):
                cover = info['thumbnails'][-1].get('url') # 尝试拿最高清的封面
            if not cover:
                cover = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500" # 兜底图
                
            # 3. 提取真实原流下载链接
            video_url = info.get('url')
            if not video_url and info.get('formats'):
                # 如果最外层没有 url，就去格式列表中寻找最后一个包含真实 url 的高清视频流
                valid_formats = [f for f in info['formats'] if f.get('url')]
                if valid_formats:
                    video_url = valid_formats[-1].get('url')
                    
            if not video_url:
                raise Exception("未找到可供直接下载的纯原音频/视频流地址")
                
            # 4. 计算/预估视频文件大小
            filesize = info.get('filesize') or info.get('filesize_approx')
            if filesize:
                size_str = f"{filesize / (1024 * 1024):.1f} MB"
            else:
                size_str = "高清原流"
                
            # 返回完全符合你前端数据结构的真实数据 JSON
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
        print(f"❌ 真实解析发生致命错误: {error_msg}")
        # 返回 500 状态码，直接触发你前端做好的“系统高倍异常拦截”弹窗，并透传真实失败原因
        raise HTTPException(status_code=500, detail=f"解析失败: {error_msg}")