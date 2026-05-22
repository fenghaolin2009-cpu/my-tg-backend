# 文件名: main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import gallery_dl  # 🚀 重磅回归：引入图文提取核心包
from gallery_dl import config as gallery_config, job as gallery_job
import requests
import uuid
import os
import re
import tempfile
import io
import contextlib  # 🚀 引入上下文管理器，用于无损捕获 gallery-dl 的模拟直链输出

# 1. 初始化纯净的 FastAPI 应用
app = FastAPI(title="SnapDownloader Pure-Link Dual-Engine Backend")

# 2. 开启全量 CORS 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 工具函数 1：正则表达式清洗过滤文本口令（剥离出干净的网址）
def utils_extract_clean_url(dirty_text: str) -> str:
    match = re.search(r"https?://[^\s]+", dirty_text)
    if match:
        return match.group(0)
    return ""


# 工具函数 2：根据网址从环境变量动态生成临时 Cookie 文件（作为匿名失败时的终极后备兜底隐藏手段）
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
    return {"status": "ok", "message": "双引擎纯直链解析开放网关正在全速运行中..."}


# 3. 核心接口：双引擎盲测全开放纯直链提取接口
@app.post("/api/v1/extract")
async def extract_stream(request: Request):
    current_cookie_path = ""
    try:
        raw_body = await request.body()
        dirty_input = raw_body.decode("utf-8").strip()
        
        print(f"========================================")
        print(f"📥 开放直链网关收到文本请求: {dirty_input[:100]}...")
        print(f"========================================")
        
        cleaned_url = utils_extract_clean_url(dirty_input)
        if not cleaned_url or not (cleaned_url.startswith("http://") or cleaned_url.startswith("https://")):
            raise HTTPException(status_code=400, detail="未检测到合法的 http:// 或 https:// 视频或图集链接")
            
        print(f"✨ 网关清洗出纯净目标 URL: {cleaned_url}")
        
        # 激活隐藏 Cookie 物理生成（若有配置环境变量）
        current_cookie_path = utils_create_temp_cookie_file(cleaned_url)

        # 统一准备装载解析结果的数组
        media_list = []
        
        # 🚀 【核心修复点一：智能双引擎盲测分流】
        try:
            # Step A: 盲测第一步，检查该域名是否属于 gallery-dl 原生支持的高清图文提取范围
            extractor = gallery_dl.extractor.find(cleaned_url)
            if extractor is None:
                raise ValueError("gallery-dl 盲测未匹配，转交二次防御视频流引擎")
            
            # 配置 gallery-dl 为纯模拟提取（不落盘、不下载文件）模式，仅吐出直链数据
            gallery_config.load()
            gallery_config.set(("output",), "mode", "url") # 强制令其只在控制台输出解析出的原图直链
            if current_cookie_path:
                gallery_config.set(("extractor",), "cookies", current_cookie_path)
                
            print(f"📸 [双引擎分流] gallery-dl 成功拦截！正在启动【非下载模拟模式】深度剥离图集直链...")
            
            # 利用 Python 标准库重定向技术，完美、无损地捕获 gallery-dl 在内存中吐出的全部直链文本
            capture_stream = io.StringIO()
            with contextlib.redirect_stdout(capture_stream):
                job = gallery_job.DataJob(cleaned_url)
                job.run()
                
            # 整理提取出来的文本行
            output_lines = capture_stream.getvalue().splitlines()
            for line in output_lines:
                clean_line = line.strip()
                # 只要是以 http 开头的连续字符串，皆判定为成功剥离的高清原图 CDN 真实网址
                if clean_line.startswith("http://") or clean_line.startswith("https://"):
                    # 智能化检测后缀，防止部分图文帖子内部夹杂短视频
                    is_video_file = any(ext in clean_line.lower() for ext in [".mp4", ".m3u8", ".mov", ".webm"])
                    media_list.append({
                        "type": "video" if is_video_file else "image",
                        "url": clean_line
                    })
            
            if not media_list:
                raise ValueError("gallery-dl 在该页面中未能捕获到可用的图片直链数据")
            print(f"🎯 [gallery-dl 提取成功] 共成功剥离出 {len(media_list)} 个高清图文直链")

        except Exception as gallery_err:
            # Step B: gallery-dl 报错或判定不是纯图文，立刻无缝转交给 yt-dlp 视频大厂引擎接管
            print(f"ℹ️ gallery-dl 探测未通过，全自动流向二次防御网：yt-dlp 视频流引擎。原因: {gallery_err}")
            
            # 配置 yt-dlp 核心参数（绝对禁止下载，只抓取直链元数据）
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,      # 核心：大门全开绝不落盘
                'extract_flat': False,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                },
                # 🚀 【核心修复点三】：强力注入特制 YouTube 移动端指纹伪装，绝不遗漏，完美穿透机房常规拦截
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web_creator']
                    }
                }
            }
            if current_cookie_path:
                ydl_opts['cookiefile'] = current_cookie_path
                
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(cleaned_url, download=False)
                
                # 场景一：多视频/多媒体（Entries 存在）
                if 'entries' in info and info['entries']:
                    for entry in info['entries']:
                        if not entry: continue
                        url = entry.get('url')
                        if not url and entry.get('formats'):
                            valid_formats = [f for f in entry['formats'] if f.get('url')]
                            if valid_formats: url = valid_formats[-1].get('url')
                        if not url: url = entry.get('thumbnail')
                        
                        if url:
                            is_video = entry.get('ext') in ['mp4', 'm3u8', 'mov', 'webm', 'flv'] or (entry.get('vcodec') and entry.get('vcodec') != 'none') or any(x in url.lower() for x in ['.mp4', '.m3u8', '.mov', 'video'])
                            media_list.append({
                                "type": "video" if is_video else "image",
                                "url": url
                            })
                # 场景二：常规单媒体（纯单视频或纯单图）
                else:
                    url = info.get('url')
                    if not url and info.get('formats'):
                        valid_formats = [f for f in info['formats'] if f.get('url')]
                        if valid_formats: url = valid_formats[-1].get('url')
                            
                    if url:
                        is_video = True
                        if info.get('ext') in ['jpg', 'png', 'jpeg', 'webp'] or any(x in url.lower() for x in ['.jpg', '.jpeg', '.png', '.webp']):
                            is_video = False
                        media_list.append({
                            "type": "video" if is_video else "image",
                            "url": url
                        })
            
            if not media_list:
                raise Exception("双引擎盲测均未能从该页面中提取到任何有效的媒体高清直链地址")
            print(f"🎯 [yt-dlp 提取成功] 共成功挖掘出 {len(media_list)} 个无损流媒体直链")

        # 🚀 【核心修复点四】：严格按照你给出的最新前端工业级响应规范返回 JSON 体
        return {
            "code": 200,
            "msg": "success",
            "data": media_list
        }
            
    except HTTPException:
        raise
    except Exception as e:
        # 保持全套高情商风控中文报错拦截（大小写不敏感匹配）
        error_msg_raw = str(e)
        error_msg_lower = error_msg_raw.lower()
        print(f"❌ 双引擎全链路崩溃，截获原因为: {error_msg_raw}")
        
        if "cookies" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🚨 当前海外服务器 IP 被平台风控拦截，请稍后再试或更换其他平台链接（如 TikTok/B站）。")
        if "twitter" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🔒 推特 (X) 官方触发了海外公共机房 IP 匿名访问限制，请稍后重试。")
        if "instagram" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🔒 本次 Instagram 访问请求被官方安全验证拦截，请更换其他链接或稍后再试。")
            
        raise HTTPException(status_code=500, detail=f"全球流媒体开放网关双引擎提取失败，请检查链接公开可访问性: {error_msg_raw}")
    finally:
        if current_cookie_path:
            utils_safe_remove_cookie_file(current_cookie_path)


# 4. 🚀 【核心修复点五】：统一留存中转代理透传接口（路径完全贴合前端所要求的 proxy-download）
@app.get("/api/v1/proxy-download")
def proxy_download(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="缺少必要的 url 参数")
        
    print(f"📥 requests 跨域中转网关接管，正在实时流式搬运资源...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }
    
    # 动态智能追加对应的防盗链钥匙 Referer
    url_lower = url.lower()
    if "tiktok.com" in url_lower:
        headers["Referer"] = "https://www.tiktok.com/"
    elif "instagram.com" in url_lower:
        headers["Referer"] = "https://www.instagram.com/"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        headers["Referer"] = "https://x.com/"
        
    try:
        # 使用 requests.get 并设置 stream=True 启动纯内存长连接实时字节搬运，物理硬盘永远 0% 占用
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        
        if response.status_code != 200:
            print(f"🚨 requests 跨域搬运握手失败，目标 CDN 状态码: {response.status_code}")
            raise HTTPException(status_code=response.status_code, detail=f"目标直链响应异常，状态码: {response.status_code}")
            
        # 建立分块生成器，每次运送 64KB 二进制碎片，保障高并发不爆内存
        def chunk_generator():
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk
                    
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        filename = "file.mp4" if "video" in content_type.lower() else "image.jpg"
        
        # 强制通知浏览器执行下载保存动作
        return StreamingResponse(
            chunk_generator(),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"🚨 中转代理网络层发生不可逆崩溃: {e}")
        raise HTTPException(status_code=500, detail=f"后端免跨域流式中转失败: {str(e)}")