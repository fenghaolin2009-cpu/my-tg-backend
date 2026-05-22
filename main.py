# 文件名: main.py
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import yt_dlp
import gallery_dl  # 引入图文开放路由盲测引擎
from gallery_dl import config as gallery_config, job as gallery_job
import uuid
import os
import re
import zipfile
import shutil
import tempfile  # 智能引入跨平台临时目录库，在 Ubuntu/Render 上会自动指向 /tmp

# 1. 初始化纯净的 FastAPI 应用（彻底移除 mangum）
app = FastAPI(title="SnapDownloader Standard Server Backend")

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


# 后台清理函数 1：图文专属阅后即焚（传输完毕后彻底删除临时目录和 ZIP 包，保持硬盘干净）
def cleanup_gallery_task(directory: str, zip_file: str):
    try:
        if os.path.exists(directory):
            shutil.rmtree(directory)
            print(f"🗑️ [常规服务器 阅后即焚] 临时图集原图目录已绝对擦除: {directory}")
        if os.path.exists(zip_file):
            os.remove(zip_file)
            print(f"🗑️ [常规服务器 阅后即焚] 临时图集 ZIP 压缩包已绝对擦除: {zip_file}")
    except Exception as cleanup_err:
        print(f"❌ [常规服务器 阅后即焚] 清理图集暂存失败: {cleanup_err}")


# 后台清理函数 2：视频专属阅后即焚
def cleanup_video_task(file_path: str):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ [常规服务器 阅后即焚] 临时视频文件已绝对擦除: {file_path}")
    except Exception as cleanup_err:
        print(f"❌ [常规服务器 阅后即焚] 清理视频暂存失败: {cleanup_err}")


# 工具函数 1：正则表达式清洗过滤文本口令（捞出首个包含 http/https 的纯网址）
def utils_extract_clean_url(dirty_text: str) -> str:
    match = re.search(r"https?://[^\s]+", dirty_text)
    if match:
        return match.group(0)
    return ""


# 工具函数 2：根据网址从环境变量动态生成临时 Cookie 文件（隐藏兜底防线）
def utils_create_temp_cookie_file(url: str) -> str:
    url_lower = url.lower()
    cookie_text = ""
    if "instagram.com" in url_lower:
        cookie_text = os.getenv("IG_COOKIE_TEXT", "")
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        cookie_text = os.getenv("TWITTER_COOKIE_TEXT", "")
        
    if cookie_text.strip():
        try:
            temp_dir = tempfile.gettempdir()
            cookie_filename = f"cookie_auth_{uuid.uuid4()}.txt"
            cookie_path = os.path.join(temp_dir, cookie_filename)
            with open(cookie_path, "w", encoding="utf-8") as f:
                f.write(cookie_text.strip())
            return cookie_path
        except Exception as e:
            print(f"⚠️ 动态生成临时 Cookie 失败: {e}")
    return ""


# 工具函数 3：强力就地销毁临时 Cookie 凭证
def utils_safe_remove_cookie_file(cookie_path: str):
    if cookie_path and os.path.exists(cookie_path):
        try:
            os.remove(cookie_path)
            print(f"🔒 [安全释放] 临时验证 Cookie 凭证已从磁盘销毁: {cookie_path}")
        except Exception as e:
            print(f"❌ 销毁临时 Cookie 失败: {e}")


# 健康检查接口
@app.get("/")
@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "ok", 
        "message": "标准独享服务器通用流媒体盲测分流服务正常运行中...",
        "active_tasks": len(DOWNLOAD_CACHE)
    }


# 4. 全开放智能路由器提取接口
@app.post("/api/v1/extract")
async def extract_stream(request: Request):
    current_cookie_path = ""
    try:
        raw_body = await request.body()
        dirty_input = raw_body.decode("utf-8").strip()
        
        print(f"========================================")
        print(f"📥 全开放路由器收到文本请求: {dirty_input[:100]}...")
        print(f"========================================")
        
        cleaned_url = utils_extract_clean_url(dirty_input)
        
        # 大门全开验证
        if not cleaned_url or not (cleaned_url.startswith("http://") or cleaned_url.startswith("https://")):
            raise HTTPException(status_code=400, detail="未检测到合法的 http:// 或 https:// 视频或图集链接")
            
        print(f"✨ 开放网关清洗出目标 URL: {cleaned_url}")
        
        # 激活隐藏 Cookie 物理生成（如果配置了环境变量）
        current_cookie_path = utils_create_temp_cookie_file(cleaned_url)

        # 初始化基础响应元数据模板
        task_type = "video"
        title = "全球全能路由器高速解析内容"
        cover = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500"
        size_str = "高清原流"
        
        # 双引擎智能盲测分流逻辑
        try:
            # Step A: 优先使用 gallery-dl 底层引擎探测是否属于其原生识别的图集
            extractor = gallery_dl.extractor.find(cleaned_url)
            if extractor is None:
                raise ValueError("gallery-dl 盲测未匹配，该平台不属于其原生图文写真提取范围")
            
            task_type = "image"
            title = f"📸 专属全能高清图文图集 ({cleaned_url.split('//')[-1].split('/')[0]})"
            size_str = "图文图集"
            print(f"🎯 [盲测分流] gallery-dl 匹配成功，系统挂载为【纯图文/照片墙】序列")
            
        except Exception as gallery_err:
            # Step B: gallery-dl 识别失败，平滑向二次防御网：yt-dlp 视频大厂引擎接管
            print(f"ℹ️ gallery-dl 探测未通过，转交 yt-dlp 视频流引擎。原因: {gallery_err}")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': False,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                }
            }
            if current_cookie_path:
                ydl_opts['cookiefile'] = current_cookie_path
                
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(cleaned_url, download=False)
                title = info.get('title', title)
                cover = info.get('thumbnail') or cover
                if not cover and info.get('thumbnails'):
                    cover = info['thumbnails'][-1].get('url')
                filesize = info.get('filesize') or info.get('filesize_approx')
                if filesize:
                    size_str = f"{filesize / (1024 * 1024):.1f} MB"
                
                # 特殊 playlist 或纯图集微调判定
                if info.get('entries') or info.get('_type') == 'playlist' or (not info.get('url') and not any(f.get('vcodec') != 'none' for f in info.get('formats', []))):
                    task_type = "image"
                    size_str = "图文图集"
                    print(f"🔄 [动态微调] yt-dlp 指纹特征识别其为播放列表或纯图集，重置为【image】")
                else:
                    task_type = "video"
                    print(f"🎯 [盲测分流] yt-dlp 识别成功，系统挂载为【无损视频原流】序列")

        # 登记缓存任务
        task_id = str(uuid.uuid4())[:12]
        DOWNLOAD_CACHE[task_id] = {
            "original_url": cleaned_url,
            "type": task_type
        }
        
        print(f"🔑 全局注册任务 ID: {task_id}，流媒体形态: {task_type}")
        
        base_url = str(request.base_url).rstrip('/')
        proxy_download_url = f"{base_url}/api/v1/download?id={task_id}"
        
        return {
          "type": task_type,
          "title": title,
          "size": size_str,
          "cover": cover,
          "actions": [
            { 
              "type": "primary", 
              "label": "🟢 高速打包下载" if task_type == "image" else "🟢 高速无损下载", 
              "url": proxy_download_url 
            }
          ]
        }
            
    except HTTPException:
        raise
    except Exception as e:
        # 全链路高情商大厂风控优雅报错拦截（大小写不敏感匹配）
        error_msg_raw = str(e)
        error_msg_lower = error_msg_raw.lower()
        print(f"❌ 盲测崩溃，风控层截获原因: {error_msg_raw}")
        
        if "cookies" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🚨 当前海外服务器 IP 被平台风控拦截，请稍后再试或更换其他平台链接（如 TikTok/B站）。")
        if "twitter" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🔒 推特 (X) 官方触发了海外公共机房 IP 匿名访问限制，请稍后重试。")
        if "instagram" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🔒 本次 Instagram 访问请求被官方安全验证拦截，请更换其他链接或稍后再试.")
            
        raise HTTPException(status_code=500, detail=f"全球流媒体网关未能识别或成功嗅探此网址，请检查链接公开可访问性: {error_msg_raw}")
    finally:
        if current_cookie_path:
            utils_safe_remove_cookie_file(current_cookie_path)


# 5. 标准常规服务器同步中转下载落盘接口
@app.get("/api/v1/download")
def proxy_download(id: str, background_tasks: BackgroundTasks):
    if not id or id not in DOWNLOAD_CACHE:
        raise HTTPException(status_code=404, detail="下载任务已失效或服务器已重启，请回前端重新解析")
        
    task_info = DOWNLOAD_CACHE[id]
    original_url = task_info["original_url"]
    task_type = task_info["type"]
    
    print(f"🚀 [标准落盘启动] 目标流: {original_url}，数据形态: {task_type}")
    current_cookie_path = utils_create_temp_cookie_file(original_url)
    temp_dir = tempfile.gettempdir()  # 在 Linux/Render 上自动获取并指向 /tmp 目录
    
    # ---------------- 📸 分支 A：纯图文/照片墙处理流 (gallery-dl) ----------------
    if task_type == "image":
        task_dir = os.path.join(temp_dir, f"gallery_{id}")
        zip_path = os.path.join(temp_dir, f"images_{id}.zip")
        os.makedirs(task_dir, exist_ok=True)
        
        try:
            gallery_config.load()
            gallery_config.set(("extractor",), "base-directory", task_dir)
            if current_cookie_path:
                gallery_config.set(("extractor",), "cookies", current_cookie_path)
                
            print(f"📥 gallery-dl 落盘执行图片拉取...")
            gallery_job.DownloadJob(original_url).run()
            
            # 使用 zipfile 压缩归丁
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                has_files = False
                for root, dirs, files in os.walk(task_dir):
                    for file in files:
                        has_files = True
                        file_full_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_full_path, task_dir)
                        zipf.write(file_full_path, arcname)
                        
            if not has_files or not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
                raise Exception("gallery-dl 开放提取引擎未能在此页面成功剥离出图片")
                
            print(f"🟢 服务器图集打包压缩成功！ZIP 大小: {os.path.getsize(zip_path)/(1024*1024):.2f} MB")
            
            # 注册“阅后即焚”后台任务，传输完毕后由 FastAPI 自动在后台擦除
            background_tasks.add_task(cleanup_gallery_task, task_dir, zip_path)
            
            return FileResponse(
                path=zip_path,
                media_type="application/zip",
                filename="images.zip"
            )
            
        except Exception as e:
            cleanup_gallery_task(task_dir, zip_path)  # 出错立即清空残渣
            error_msg_raw = str(e)
            error_msg_lower = error_msg_raw.lower()
            if "cookies" in error_msg_lower:
                raise HTTPException(status_code=400, detail="🚨 当前海外服务器 IP 被平台风控拦截，请稍后再试或更换其他平台链接（如 TikTok/B站）。")
            raise HTTPException(status_code=500, detail=f"图集打包暂存失败: {error_msg_raw}")
        finally:
            if current_cookie_path:
                utils_safe_remove_cookie_file(current_cookie_path)

    # ---------------- 📹 分支 B：流媒体视频处理流 (yt-dlp) ----------------
    else:
        file_path = os.path.join(temp_dir, f"snap_{id}.mp4")
        ydl_opts = {
            'outtmpl': file_path,
            'format': 'best[ext=mp4]/best/mp4',  # 免登录基础兼容 MP4 独立单格式封装，确保高通过率
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            }
        }
        if current_cookie_path:
            ydl_opts['cookiefile'] = current_cookie_path
            
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([original_url])
                
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                raise Exception("yt-dlp 下载引擎未能成功在服务器生成视频实体")
                
            print(f"🟢 服务器视频实体落盘成功！暂存路径: {file_path}")
            
            # 注册“阅后即焚”后台视频清理任务
            background_tasks.add_task(cleanup_video_task, file_path)
            
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
            if "cookies" in error_msg_lower:
                raise HTTPException(status_code=400, detail="🚨 当前海外服务器 IP 被平台风控拦截，请稍后再试或更换其他平台链接（如 TikTok/B站）。")
            if "twitter" in error_msg_lower and "no video" in error_msg_lower:
                raise HTTPException(status_code=400, detail="🔒 推特 (X) 官方触发了海外公共机房 IP 匿名访问限制，请稍后重试。")
            if "instagram" in error_msg_lower and "no video" in error_msg_lower:
                raise HTTPException(status_code=400, detail="🔒 本次 Instagram 访问请求被官方安全验证拦截，请更换其他链接或稍后再试。")
                
            raise HTTPException(status_code=500, detail=f"视频落盘暂存失败: {error_msg_raw}")
        finally:
            if current_cookie_path:
                utils_safe_remove_cookie_file(current_cookie_path)