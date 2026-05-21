# 文件名: main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from urllib.parse import quote
import yt_dlp
import httpx

# 1. 初始化 FastAPI 应用
app = FastAPI(title="SnapDownloader Advanced Proxy Backend")

# 2. 开启全量 CORS 跨域配置
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
    return {"status": "ok", "message": "视频流解析及中转下载服务正在运行中..."}


# 4. 真实原流提取接口（已修改：返回经过后端中转的下载链接）
@app.post("/api/v1/extract")
async def extract_stream(request: Request):
    try:
        # 直接读取前端发送的裸文本（text/plain）请求体
        raw_body = await request.body()
        url_input = raw_body.decode("utf-8").strip()
        
        print(f"========================================")
        print(f"📡 收到前端裸文本解析请求: {url_input}")
        print(f"========================================")
        
        if not url_input:
            raise HTTPException(status_code=400, detail="输入的视频网址不能为空")
            
        # 配置 yt-dlp 核心参数（保留原有的 YouTube 常规防拦截配置）
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android', 'web_embedded']
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url_input, download=False)
            
            title = info.get('title', '未命名原流视频')
            
            cover = info.get('thumbnail')
            if not cover and info.get('thumbnails'):
                cover = info['thumbnails'][-1].get('url')
            if not cover:
                cover = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500"
                
            video_url = info.get('url')
            if not video_url and info.get('formats'):
                valid_formats = [f for f in info['formats'] if f.get('url')]
                if valid_formats:
                    video_url = valid_formats[-1].get('url')
                    
            if not video_url:
                raise Exception("无法从该页面中提取出有效的原音频/视频无水印直链地址")
                
            filesize = info.get('filesize') or info.get('filesize_approx')
            if filesize:
                size_str = f"{filesize / (1024 * 1024):.1f} MB"
            else:
                size_str = "高清原流"
                
            # --- 【核心修改点】智能化动态拼接后端代理下载链接 ---
            # 1. 自动获取当前后端的根域名（不论是 localhost 还是 Render 域名都会自动适配）
            base_url = str(request.base_url).rstrip('/')
            # 2. 对复杂的 CDN 真实网址进行安全编码，防止 CDN 网址内部的 &、? 符号搞乱链接结构
            encoded_video_url = quote(video_url, safe='')
            # 3. 拼接成指向我们自己后端 /api/v1/download 接口的专享中转链接
            proxy_download_url = f"{base_url}/api/v1/download?url={encoded_video_url}"
            
            return {
                "type": "video",
                "title": title,
                "size": size_str,
                "cover": cover,
                "actions": [
                    { "type": "primary", "label": "🟢 高速无损下载", "url": proxy_download_url }
                ]
            }
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 解析服务崩溃，异常原因: {error_msg}")
        raise HTTPException(status_code=500, detail=f"解析失败: {error_msg}")


# 5. 新增：反向代理流式中转下载接口（解决 TikTok 等防盗链 404 问题）
@app.get("/api/v1/download")
async def proxy_download(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="缺少必要的 url 参数")
        
    print(f"📥 后端正在流式中转下载 CDN 资源: {url[:60]}...")
    
    # 为请求 TikTok/小红书等 CDN 加上常规反爬伪装请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Encoding': 'identity',
    }
    
    # 创建一个实时读取二进制数据流的生成器
    async def stream_generator():
        # follow_redirects=True 允许自动追踪 CDN 内部的重定向跳转
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                async with client.stream("GET", url, headers=headers) as response:
                    if response.status_code != 200:
                        raise HTTPException(status_code=response.status_code, detail="CDN 资源请求失败，请稍后重试")
                    
                    # 每次抓取 64KB 的视频碎片，实时发送给前端浏览器
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        yield chunk
            except Exception as e:
                print(f"❌ 中转流式下载中途发生断开或异常: {e}")
                
    # 强制让前端浏览器弹出“保存文件”的高速无损下载框
    return StreamingResponse(
        stream_generator(),
        media_type="video/mp4",
        headers={
            "Content-Disposition": "attachment; filename=video.mp4"
        }
    )