# 文件名: main.py
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from mangum import Mangum
import yt_dlp
import gallery_dl  # 🚀 引入核心包，用于全开放式路由器路由盲测
from gallery_dl import config as gallery_config, job as gallery_job
import uuid
import os
import re
import zipfile
import shutil

# 1. 初始化 FastAPI 应用
app = FastAPI(title="SnapDownloader Universal Open-Router Backend")

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


# 后台清理函数 1：图文专属阅后即焚（彻底删除临时目录和 ZIP 包，严防 AWS Lambda 爆盘）
def cleanup_gallery_task(directory: str, zip_file: str):
    try:
        if os.path.exists(directory):
            shutil.rmtree(directory)
            print(f"🗑️ [Serverless 阅后即焚] 临时图集原图目录已绝对擦除: {directory}")
        if os.path.exists(zip_file):
            os.remove(zip_file)
            print(f"🗑️ [Serverless 阅后即焚] 临时图集 ZIP 压缩包已绝对擦除: {zip_file}")
    except Exception as cleanup_err:
        print(f"❌ [Serverless 阅后即焚] 清理图集暂存失败: {cleanup_err}")


# 后台清理函数 2：视频专属阅后即焚
def cleanup_video_task(file_path: str):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ [Serverless 阅后即焚] 临时视频文件已绝对擦除: {file_path}")
    except Exception as cleanup_err:
        print(f"❌ [Serverless 阅后即焚] 清理视频暂存失败: {cleanup_err}")


# 工具函数 1：正则表达式清洗过滤文本口令（捞出首个包含 http/https 的文本块）
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
            cookie_filename = f"cookie_auth_{uuid.uuid4()}.txt"
            cookie_path = os.path.join("/tmp", cookie_filename)
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
        "message": "全球全能流媒体全开放路由盲测分流服务已全面就绪",
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
        
        # 🚀 【核心优化点 1：大门全开】取消具体域名限制，只要是常规 http/https 协议网址全部予以接纳放行
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
        
        # 🚀 【核心优化点 2：双引擎智能盲测分流】
        try:
            # Step 2a: 盲测第一步，默认扔给 gallery-dl 的底层引擎寻找匹配的图集抓取类
            extractor = gallery_dl.extractor.find(cleaned_url)
            if extractor is None:
                # 如果 gallery-dl 核心组件不认识此域名，主动抛出异常，逼迫其流向 except 块
                raise ValueError("gallery-dl 盲测未匹配，该平台不属于其原生图文写真提取范围")
            
            # gallery-dl 盲测成功，说明该平台属于它原生支持的高清图文/照片墙帖子
            task_type = "image"
            title = f"📸 专属全能高清图文图集 ({cleaned_url.split('//')[-1].split('/')[0]})"
            size_str = "图文图集"
            print(f"🎯 [盲测分流大成功] gallery-dl 完美拦截此 URL，系统自动挂载为【纯图文/照片墙】序列")
            
        except Exception as gallery_err:
            # Step 2b: gallery-dl 识别失败或抛出异常，立刻就地转交给 yt-dlp 视频大厂引擎接管
            print(f"ℹ️ gallery-dl 探测未通过，全自动流向二次防御网：yt-dlp 视频流引擎。原因: {gallery_err}")
            
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
                
            # 执行二次提取，如果这里再次报错，将直接震碎内部 try 块，坠入外部的大厂风控捕获逻辑中
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(cleaned_url, download=False)
                title = info.get('title', title)
                cover = info.get('thumbnail') or cover
                if not cover and info.get('thumbnails'):
                    cover = info['thumbnails'][-1].get('url')
                filesize = info.get('filesize') or info.get('filesize_approx')
                if filesize:
                    size_str = f"{filesize / (1024 * 1024):.1f} MB"
                
                # 针对部分综合平台的特殊情况（如 yt-dlp 把多图帖子识别为 playlist 或无直接 url 的特殊流）
                if info.get('entries') or info.get('_type') == 'playlist' or (not info.get('url') and not any(f.get('vcodec') != 'none' for f in info.get('formats', []))):
                    task_type = "image"
                    size_str = "图文图集"
                    print(f"🔄 [动态微调] yt-dlp 二次指纹特征识别其为播放列表或纯图集，数据类型安全重置为【image】")
                else:
                    task_type = "video"
                    print(f"🎯 [盲测分流大成功] yt-dlp 视频引擎完美拦截此 URL，系统自动挂载为【无损视频原流】序列")

        # 5. 登记缓存任务（此时不管是哪个引擎接管的，original_url 都是完美清洗干净的纯网址）
        task_id = str(uuid.uuid4())[:12]
        DOWNLOAD_CACHE[task_id] = {
            "original_url": cleaned_url,
            "type": task_type
        }
        
        print(f"🔑 路由分流归档完毕！全局注册任务 ID: {task_id}，流媒体形态: {task_type}")
        
        # 动态组装指向云函数当前路由的动态网关直链
        base_url = str(request.base_url).rstrip('/')
        proxy_download_url = f"{base_url}/api/v1/download?id={task_id}"
        
        # 完美适配并返回你前端所需的纯净 JSON 格式
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
        # 🚀 【核心优化点 3：全链路风控平替网关】
        # 只要双引擎盲测链条彻底断裂崩溃，便会在此集中触发对各大国际/国内平台的机房 IP 优雅中文拦截
        error_msg_raw = str(e)
        error_msg_lower = error_msg_raw.lower()
        print(f"❌ 盲测链条双重崩溃，风控感知层截获原因: {error_msg_raw}")
        
        if "cookies" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🚨 当前海外服务器 IP 被平台风控拦截，请稍后再试或更换其他平台链接（如 TikTok/B站）。")
        if "twitter" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🔒 推特 (X) 官方触发了海外公共机房 IP 匿名访问限制，请稍后重试。")
        if "instagram" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🔒 本次 Instagram 访问请求被官方安全验证拦截，请更换其他链接或稍后再试。")
            
        raise HTTPException(status_code=500, detail=f"全球流媒体网关未能识别或成功嗅探此网址，请检查链接公开可访问性: {error_msg_raw}")
    finally:
        if current_cookie_path:
            utils_safe_remove_cookie_file(current_cookie_path)


# 5. 云函数同步中转下载落盘接口（完美复用双引擎，自带严格的分身复用 Warm Start 盘符爆炸清理保护）
@app.get("/api/v1/download")
def proxy_download(id: str, background_tasks: BackgroundTasks):
    if not id or id not in DOWNLOAD_CACHE:
        raise HTTPException(status_code=404, detail="下载任务已失效或服务器已重启，请回前端重新解析")
        
    task_info = DOWNLOAD_CACHE[id]
    original_url = task_info["original_url"]
    task_type = task_info["type"]
    
    print(f"🚀 [Lambda 物理隔离落盘启动] 目标流: {original_url}，数据形态: {task_type}")
    current_cookie_path = utils_create_temp_cookie_file(original_url)
    
    # ---------------- 📸 分支 A：纯图文/照片墙处理流 (gallery-dl) ----------------
    if task_type == "image":
        # 强行在 Lambda 的 /tmp 目录下建立专享随机子文件夹隔离层，防止高并发容器复用时文件串流
        task_dir = os.path.join("/tmp", f"gallery_{id}")
        zip_path = os.path.join("/tmp", f"images_{id}.zip")
        os.makedirs(task_dir, exist_ok=True)
        
        try:
            gallery_config.load()
            gallery_config.set(("extractor",), "base-directory", task_dir)
            if current_cookie_path:
                gallery_config.set(("extractor",), "cookies", current_cookie_path)
                
            print(f"📥 gallery-dl 全开放探测器正式落盘执行图片拉取...")
            gallery_job.DownloadJob(original_url).run()
            
            # 使用 zipfile 模块将落盘的多张高清原图全自动归档压缩
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                has_files = False
                for root, dirs, files in os.walk(task_dir):
                    for file in files:
                        has_files = True
                        file_full_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_full_path, task_dir)
                        zipf.write(file_full_path, arcname)
                        
            if not has_files or not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
                raise Exception("gallery-dl 开放提取引擎未能在此页面成功剥离出图片并写成实体")
                
            print(f"🟢 云端图集打包压缩大成功！ZIP 大小: {os.path.getsize(zip_path)/(1024*1024):.2f} MB")
            
            # 🚀 【Serverless 核心：盘符防爆安全网】下发给前端的瞬间，立刻在后台清空当前分身的隔离目录与 ZIP
            background_tasks.add_task(cleanup_gallery_task, task_dir, zip_path)
            
            return FileResponse(
                path=zip_path,
                media_type="application/zip",
                filename="images.zip"
            )
            
        except Exception as e:
            cleanup_gallery_task(task_dir, zip_path)  # 发生故障就地物理扬灰，绝不霸占盘符空间
            error_msg_raw = str(e)
            error_msg_lower = error_msg_raw.lower()
            if "cookies" in error_msg_lower:
                raise HTTPException(status_code=400, detail="🚨 当前海外服务器 IP 被平台风控拦截，请稍后再试或更换其他平台链接（如 TikTok/B站）。")
            raise HTTPException(status_code=500, detail=f"云端开放图集打包暂存失败: {error_msg_raw}")
        finally:
            if current_cookie_path:
                utils_safe_remove_cookie_file(current_cookie_path)

    # ---------------- 📹 分支 B：流媒体视频处理流 (yt-dlp) ----------------
    else:
        file_path = os.path.join("/tmp", f"snap_{id}.mp4")
        ydl_opts = {
            'outtmpl': file_path,
            # 强行限定免登录基础兼容 MP4 单格式封装，打通在无 ffmpeg 的基础 Lambda 纯净容器中的直接落盘通过率
            'format': 'best[ext=mp4]/best/mp4',         
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
                raise Exception("yt-dlp 开放下载引擎未能成功在 AWS Lambda 本地生成视频实体")
                
            print(f"🟢 云端视频实体落盘成功！暂存路径: {file_path}")
            
            # 🚀 【Serverless 核心：盘符防爆安全网】下发完立刻通过线程管道彻底抹除物理痕迹
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
                
            raise HTTPException(status_code=500, detail=f"云端开放视频落盘暂存失败: {error_msg_raw}")
        finally:
            if current_cookie_path:
                utils_safe_remove_cookie_file(current_cookie_path)


# 6. 🚀 【AWS Lambda 独家分身入口】
# 完美映射接管整个全开放路由的 FastAPI 路由树，作为 Serverless 容器环境中唯一的主 Handler 触发器
handler = Mangum(app)