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
app = FastAPI(title="SnapDownloader Ultimate Cookie-Guard Backend")

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


# 后台清理函数：专门用于在视频成功下发给前端后，全自动删除落盘的临时视频文件（阅后即焚）
def cleanup_file(file_path: str):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ [阅后即焚] 临时视频文件已被安全、彻底地从硬盘删除: {file_path}")
    except Exception as cleanup_err:
        print(f"❌ [阅后即焚] 清理临时视频文件失败: {cleanup_err}")


# 工具函数 1：利用正则表达式从混杂文本中精准剥离出真正的网址
def utils_extract_clean_url(dirty_text: str) -> str:
    match = re.search(r"https?://[^\s]+", dirty_text)
    if match:
        return match.group(0)
    return ""


# 工具函数 2：【全新核心升级】根据网址智能识别，并从环境变量动态生成标准的 Netscape 临时 Cookie 文件
def utils_create_temp_cookie_file(url: str) -> str:
    url_lower = url.lower()
    cookie_text = ""
    
    # 智能识别平台
    if "instagram.com" in url_lower:
        cookie_text = os.getenv("IG_COOKIE_TEXT", "")
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        cookie_text = os.getenv("TWITTER_COOKIE_TEXT", "")
        
    # 如果对应的环境变量里存在导出的 Cookie 文本，则启动物理暂存
    if cookie_text.strip():
        try:
            temp_dir = tempfile.gettempdir()
            cookie_filename = f"cookie_auth_{uuid.uuid4()}.txt"
            cookie_path = os.path.join(temp_dir, cookie_filename)
            
            # 将多行 Netscape 文本写入服务器临时文件夹
            with open(cookie_path, "w", encoding="utf-8") as f:
                f.write(cookie_text.strip())
            return cookie_path
        except Exception as e:
            print(f"⚠️ 动态生成 Cookie 文件失败: {e}")
            
    return ""  # 如果未配置环境变量或写入失败，返回空字符串，匿名请求


# 工具函数 3：【全新核心升级】毫秒级无条件强力抹除临时 Cookie 凭证，防止隐私残留
def utils_safe_remove_cookie_file(cookie_path: str):
    if cookie_path and os.path.exists(cookie_path):
        try:
            os.remove(cookie_path)
            print(f"🔒 [安全闭合] 临时验证 Cookie 凭证已从磁盘彻底销毁: {cookie_path}")
        except Exception as e:
            print(f"❌ [安全闭合] 销毁临时 Cookie 文件失败: {e}")


# 健康检查接口
@app.get("/")
@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "ok", 
        "message": "双接口全链路 Cookie 注入及全量容错服务运行中...",
        "active_tasks": len(DOWNLOAD_CACHE)
    }


# 4. 智能提取接口（已注入 Cookie 动态生成与全自动阅后即焚）
@app.post("/api/v1/extract")
async def extract_stream(request: Request):
    # 初始化本次请求的临时 Cookie 路径变量
    current_cookie_path = ""
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
        
        # --- 【核心重构点 1】解析接口 Cookie 动态注入 ---
        current_cookie_path = utils_create_temp_cookie_file(cleaned_url)
        
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
        
        # 如果生成了对应的临时 Cookie 凭证文件，直接全量喂入 yt-dlp 核心参数中
        if current_cookie_path:
            ydl_opts['cookiefile'] = current_cookie_path
            print(f"🍪 [双管齐下] 已成功为解析提取接口挂载临时 Cookie 钥匙锁")
        
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
        error_msg_raw = str(e)
        error_msg_lower = error_msg_raw.lower()
        print(f"❌ 解析服务触发捕获，异常原因: {error_msg_raw}")
        
        if "cookies" in error_msg_lower:
            raise HTTPException(
                status_code=400, 
                detail="🚨 当前海外服务器 IP 被平台风控拦截，请稍后再试或更换其他平台链接（如 TikTok/B站）。"
            )
        if "twitter" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(
                status_code=400,
                detail="🔒 推特 (X) 官方触发了海外公共机房 IP 匿名访问限制，请稍后重试。"
            )
        if "instagram" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(
                status_code=400,
                detail="🔒 本次 Instagram 访问请求被官方安全验证拦截，请更换其他链接或稍后再试。"
            )
            
        raise HTTPException(status_code=500, detail=f"解析失败: {error_msg_raw}")
    finally:
        # --- 【核心重构点 2】坚固防线：无论解析成功还是抛出异常，毫秒级就地扬掉临时 Cookie 文件 ---
        if current_cookie_path:
            utils_safe_remove_cookie_file(current_cookie_path)


# 5. 同步中转下载接口
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
    
    # 初始化本轮下载接口的临时 Cookie 路径变量
    current_cookie_path = ""
    
    try:
        # --- 【核心重构点 3】下载接口 Cookie 动态注入 ---
        current_cookie_path = utils_create_temp_cookie_file(original_url)
        
        ydl_opts = {
            'outtmpl': file_path,
            'format': 'best[ext=mp4]/best/mp4',         
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            }
        }
        
        # 将 Cookie 文件注入下载引擎参数中
        if current_cookie_path:
            ydl_opts['cookiefile'] = current_cookie_path
            print(f"🍪 [双管齐下] 已成功为中转下载落盘接口挂载临时 Cookie 钥匙锁")
            
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
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
            
        error_msg_raw = str(e)
        error_msg_lower = error_msg_raw.lower()
        print(f"🚨 服务器本地中转发生崩溃: {error_msg_raw}")
        
        if "cookies" in error_msg_lower:
            raise HTTPException(
                status_code=400, 
                detail="🚨 当前海外服务器 IP 被平台风控拦截，请稍后再试或更换其他平台链接（如 TikTok/B站）。"
            )
        if "twitter" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(
                status_code=400,
                detail="🔒 推特 (X) 官方触发了海外公共机房 IP 匿名访问限制，请稍后重试。"
            )
        if "instagram" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(
                status_code=400,
                detail="🔒 本次 Instagram 访问请求被官方安全验证拦截，请更换其他链接或稍后再试。"
            )
            
        raise HTTPException(status_code=500, detail=f"后端实体暂存失败: {error_msg_raw}")
    finally:
        # --- 【核心重构点 4】坚固防线：即使是同步下载下载完毕或断流崩溃，同样立即就地销毁临时 Cookie 凭证 ---
        if current_cookie_path:
            utils_safe_remove_cookie_file(current_cookie_path)