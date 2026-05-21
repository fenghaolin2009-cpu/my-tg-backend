# 文件名: main.py
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import yt_dlp
import uuid
import os
import tempfile
import re

# 1. 初始化 FastAPI 应用
app = FastAPI(title="SnapDownloader V2 Ultra-Robust Backend")

# 2. 开启全量 CORS 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 全局内存下载缓存字典
DOWNLOAD_CACHE = {}


# 后台清理函数（阅后即焚）
def cleanup_file(file_path: str):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ [阅后即焚] 临时视频文件已被安全、彻底地从硬盘删除: {file_path}")
    except Exception as cleanup_err:
        print(f"❌ [阅后即焚] 清理临时文件失败: {cleanup_err}")


# 工具函数：利用正则表达式从混杂文本中精准剥离出真正的 http/https 链接
def utils_extract_clean_url(dirty_text: str) -> str:
    match = re.search(r"https?://[^\s]+", dirty_text)
    if match:
        return match.group(0)
    return ""


# 健康检查接口
@app.get("/")
@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "ok", 
        "message": "极强格式容错及优雅风控提示中转下载服务运行中...",
        "active_tasks": len(DOWNLOAD_CACHE)
    }


# 4. 智能提取接口（加入优雅风控提示拦截）
@app.post("/api/v1/extract")
async def extract_stream(request: Request):
    try:
        raw_body = await request.body()
        dirty_input = raw_body.decode("utf-8").strip()
        
        print(f"========================================")
        print(f"📥 收到前端交互原始文本:\n{dirty_input}")
        print(f"========================================")
        
        cleaned_url = utils_extract_clean_url(dirty_input)
        
        if not cleaned_url:
            raise HTTPException(status_code=400, detail="未检测到有效的视频链接，请检查输入的文本")
            
        print(f"✨ 文本脱水大成功！纯净网址为: {cleaned_url}")
        
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
            info = ydl.extract_info(cleaned_url, download=False)
            
            title = info.get('title', '未命名原流视频')
            
            cover = info.get('thumbnail')
            if not cover and info.get('thumbnails'):
                cover = info['thumbnails'][-1].get('url')
            if not cover:
                cover = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500"
                
            filesize = info.get('filesize') or info.get('filesize_approx')
            size_str = f"{filesize / (1024 * 1024):.1f} MB" if filesize else "高清原流"
            
            task_id = str(uuid.uuid4())[:12]
            DOWNLOAD_CACHE[task_id] = {
                "original_url": cleaned_url
            }
            
            print(f"🔑 任务登记成功！临时 ID: {task_id}")
            
            base_url = str(request.base_url).rstrip('/')
            proxy_download_url = f"{base_url}/api/v1/download?id={task_id}"
            
            return {
                "type": "video",
                "title": title,
                "size": size_str,
                "cover": cover,
                "actions": [
                    { "type": "primary", "label": "🟢 高速无损下载", "url": proxy_download_url }
                ]
            }
            
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 解析服务崩溃，异常原因: {error_msg}")
        
        # 🚀 【核心优化一】：捕获并降级抖音风控拦截报错，返回前端清晰直观的 400 温馨中文原理解释
        if "cookies" in error_msg.lower():
            raise HTTPException(
                status_code=400, 
                detail="🚨 当前海外服务器 IP 被平台风控拦截，请稍后再试或更换其他平台链接（如 TikTok/B站）。"
            )
            
        raise HTTPException(status_code=500, detail=f"解析失败: {error_msg}")


# 5. 同步中转下载接口（加入 B 站基础单文件格式容错）
@app.get("/api/v1/download")
def proxy_download(id: str, background_tasks: BackgroundTasks):
    if not id:
        raise HTTPException(status_code=400, detail="缺少必要的 id 参数")
        
    if id not in DOWNLOAD_CACHE:
        raise HTTPException(status_code=404, detail="下载任务已失效或服务器已重启，请回前端重新解析")
        
    original_url = DOWNLOAD_CACHE[id]["original_url"]
    print(f"🚀 [物理落盘启动] 正在调用已清洗网址启动下载: {original_url}")
    
    temp_dir = tempfile.gettempdir()
    file_name = f"snap_{uuid.uuid4()}.mp4"
    file_path = os.path.join(temp_dir, file_name)
    
    ydl_opts = {
        'outtmpl': file_path,
        # 🚀 【核心优化二】：强制指定匿名、最基础、无需登录即可获取的单文件格式
        # 告诉引擎不要盲目挑剔画质，优先选择已经封装好的 mp4 单文件，完美平替并治愈 B 站的 Requested format 崩溃报错
        'format': 'best[ext=mp4]/best/mp4',         
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([original_url])
            
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            raise Exception("yt-dlp 下载引擎未能成功在服务器生成有效的实体文件")
            
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        print(f"🟢 物理暂存大成功！文件大小: {file_size_mb:.2f} MB，路径: {file_path}")
        
        background_tasks.add_task(cleanup_file, file_path)
        
        return FileResponse(
            path=file_path,
            media_type="video/mp4",
            filename="video.mp4"
        )
        
    except Exception as e:
        error_msg = str(e)
        print(f"🚨 服务器本地中转发生致命崩溃: {error_msg}")
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
            
        # 🚀 【核心优化三】：若在中转下载环节才触发 Cookies 封锁，同样优雅降级弹出温馨中文提示
        if "cookies" in error_msg.lower():
            raise HTTPException(
                status_code=400, 
                detail="🚨 当前海外服务器 IP 被平台风控拦截，请稍后再试或更换其他平台链接（如 TikTok/B站）。"
            )
            
        raise HTTPException(status_code=500, detail=f"后端实体暂存失败: {error_msg}")