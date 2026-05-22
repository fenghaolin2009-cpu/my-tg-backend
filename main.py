# 文件名: main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import requests
import uuid
import os
import re
import tempfile
import subprocess

# 1. 初始化纯净的 FastAPI 应用
app = FastAPI(title="SnapDownloader Pure-Link Anti-M3U8 Backend")

# 2. 开启全量 CORS 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 工具函数 1：正则表达式清洗过滤文本口令（剥离出纯净网址）
def utils_extract_clean_url(dirty_text: str) -> str:
    match = re.search(r"https?://[^\s]+", dirty_text)
    if match:
        return match.group(0)
    return ""


# 工具函数 2：根据网址从环境变量动态生成临时 Cookie 文件
def utils_create_temp_cookie_file(url: str) -> str:
    url_lower = url.lower()
    cookie_text = ""
    if "instagram.com" in url_lower:
        cookie_text = os.getenv("IG_COOKIE_TEXT", "")
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        cookie_text = os.getenv("TWITTER_COOKIE_TEXT", "")
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        cookie_text = os.getenv("YOUTUBE_COOKIE_TEXT", "")

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
    return {"status": "ok", "message": "终结 2KB 骗子文件！全球流媒体开放网关全量平稳运行中..."}


# 3. 核心接口：双引擎串联协同无损流水线提取接口
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

        # 【洗白模块】：域名强行洗白
        if "x.com" in cleaned_url.lower():
            cleaned_url = cleaned_url.replace("x.com", "twitter.com").replace("X.com", "twitter.com")
            print(f"🔄 [域名洗白] 检测到 x.com 域名，已强行修正替换为 twitter.com 以激活核心解析器规则")

        print(f"✨ 网关清洗后送入流水线的最终 URL: {cleaned_url}")

        # 激活隐藏 Cookie 物理生成
        current_cookie_path = utils_create_temp_cookie_file(cleaned_url)

        # 统一准备装载解析结果的数组
        media_list = []

        # ==========================================
        # 【阶段一：资产初筛搜刮 (工业级系统管道版)】
        # ==========================================
        try:
            cmd = ["gallery-dl", "-g", cleaned_url]
            if current_cookie_path and not any(yt_domain in cleaned_url.lower() for yt_domain in ["youtube.com", "youtu.be"]):
                cmd.extend(["--cookies", current_cookie_path])

            if not any(yt_domain in cleaned_url.lower() for yt_domain in ["youtube.com", "youtu.be"]):
                print(f"📸 [阶段一] 启动系统级进程调用 gallery-dl CLI: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
                
                output_lines = result.stdout.splitlines()
                for line in output_lines:
                    clean_line = line.strip()
                    if clean_line.startswith("http://") or clean_line.startswith("https://"):
                        is_video_file = any(ext in clean_line.lower() for ext in [".mp4", ".m3u8", ".mov", ".webm"])
                        media_list.append({
                            "type": "video" if is_video_file else "image",
                            "url": clean_line
                        })
                print(f"🎯 [阶段一完成] 进程内核成功捕获到 {len(media_list)} 个原始资产节点")
        except Exception as gallery_err:
            print(f"ℹ️ [阶段一提示] gallery-dl 核心流处理跳过或遭遇风控，交由二次防御网兜底: {gallery_err}")

        # ==========================================
        # 【阶段二：高清视频重构升级与资产无损合并 (yt-dlp)】
        # ==========================================
        has_video_clue = any(m["type"] == "video" for m in media_list)
        is_major_platform = any(domain in cleaned_url.lower() for domain in ["twitter.com", "instagram.com", "youtube.com", "youtu.be"])

        if not media_list or has_video_clue or is_major_platform:
            print(f"🔄 [阶段二] 触发重构协同判定，正在唤醒 yt-dlp 终极雷达进行高清视频捕获...")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': False,
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'ios', 'web_creator', 'mweb', 'tv']
                    }
                }
            }
            
            if current_cookie_path:
                ydl_opts['cookiefile'] = current_cookie_path

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(cleaned_url, download=False)

                def clean_progressive_url(raw_url: str) -> str:
                    if not raw_url:
                        return ""
                    url_check = raw_url.lower()
                    if ".m3u8" in url_check or "manifest" in url_check:
                        return ""
                    return raw_url

                def resolve_pure_mp4_url(item_data) -> str:
                    direct_url = clean_progressive_url(item_data.get('url'))
                    if direct_url:
                        return direct_url

                    formats = item_data.get('formats', [])
                    valid_mp4_formats = [
                        f for f in formats
                        if f.get('url') and f.get('ext') == 'mp4' and not any(x in f.get('url').lower() for x in ['.m3u8', 'manifest'])
                    ]
                    if valid_mp4_formats:
                        combined = [f for f in valid_mp4_formats if f.get('vcodec') != 'none' and f.get('acodec') != 'none']
                        if combined:
                            return combined[-1].get('url')
                        return valid_mp4_formats[-1].get('url')

                    any_progressive = [f for f in formats if f.get('url') and not any(x in f.get('url').lower() for x in ['.m3u8', 'manifest'])]
                    if any_progressive:
                        return any_progressive[-1].get('url')
                    return ""

                yt_dlp_images = []
                def collect_thumbnails_safe(item_data):
                    thumbnails = item_data.get('thumbnails', [])
                    for t in thumbnails:
                        t_url = t.get('url', '')
                        if t_url and any(keyword in t_url for keyword in ['pbs.twimg.com/media/', 'twimg.com/media/', 'instagram.com/p/']):
                            if not any(t_url in m['url'] for m in media_list):
                                yt_dlp_images.append({"type": "image", "url": t_url})

                yt_dlp_videos = []
                if 'entries' in info and info['entries']:
                    for entry in info['entries']:
                        if not entry: continue
                        v_url = resolve_pure_mp4_url(entry)
                        if v_url:
                            yt_dlp_videos.append({"type": "video", "url": v_url})
                        collect_thumbnails_safe(entry)
                else:
                    v_url = resolve_pure_mp4_url(info)
                    if v_url:
                        yt_dlp_videos.append({"type": "video", "url": v_url})
                    collect_thumbnails_safe(info)

                retained_images = [m for m in media_list if m["type"] == "image"]
                media_list = retained_images + yt_dlp_images + yt_dlp_videos
                print(f"⚡ [重构无损拼装] 当前队列状态：留存历史大图 {len(retained_images)} 个，"
                      f"雷达捞回大图 {len(yt_dlp_images)} 个，合并并入高清纯净视频 {len(yt_dlp_videos)} 个")
            
            except Exception as ytdlp_err:
                print(f"ℹ️ [阶段二提示] yt-dlp 核心逆向遭遇非致命异常: {ytdlp_err}")

        # ==========================================
        # 【阶段三：最终收网、安全去重与 M3U8 残留拦截】
        # ==========================================
        seen_urls = set()
        final_media_list = []
        for item in media_list:
            url = item["url"]
            url_lower = url.lower()
            
            if ".m3u8" in url_lower or "manifest" in url_lower:
                continue
                
            if url not in seen_urls:
                seen_urls.add(url)
                final_media_list.append(item)

        if not final_media_list:
            raise Exception("双引擎串联协同流水线运行完毕，未能提取到任何有效的图片资产或纯净实体视频直链")

        print(f"🎯 [流水线收网] 最终资产去重清洗完成，共计输出 {len(final_media_list)} 个直链资产对象")
        
        return {
            "code": 200,
            "msg": "success",
            "data": final_media_list
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg_raw = str(e)
        error_msg_lower = error_msg_raw.lower()
        print(f"❌ 协同流水线彻底断裂，异常详情: {error_msg_raw}")

        if "cookies" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🚨 当前海外服务器 IP 被大厂风控拦截，请稍后再试，或检查后端相应平台的 Cookie 变量配置。")
        if "confirm you're not a bot" in error_msg_lower or "sign in to confirm" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🚨 YouTube 触发了最强机器人登录墙验证！请立即检查并更新 Render 后台的 YOUTUBE_COOKIE_TEXT 环境变量。")
        if "twitter" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🔒 推特 (X) 官方触发了匿名访问限制，请在 VPS / Render 配置对应的验证 Cookie。")
        if "instagram" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🔒 Instagram 访问请求被官方安全验证墙拦截，请稍后再试或更新 Cookie。")

        raise HTTPException(status_code=500, detail=f"流媒体直链网关提取失败，请检查目标链接状态: {error_msg_raw}")
    finally:
        if current_cookie_path:
            utils_safe_remove_cookie_file(current_cookie_path)


# 4. 免受 CORS 跨域防盗链困扰的 proxy-download 代理中转接口
@app.get("/api/v1/proxy-download")
def proxy_download(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="缺少必要的 url 参数")

    print(f"📥 requests 跨域中转网关接管，正在搬运实时流...")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }

    url_lower = url.lower()
    if "tiktok.com" in url_lower:
        headers["Referer"] = "https://www.tiktok.com/"
    elif "instagram.com" in url_lower:
        headers["Referer"] = "https://www.instagram.com/"
    elif "twitter.com" in url_lower or "x.com" in url_lower or "twimg.com" in url_lower:
        headers["Referer"] = "https://x.com/"

    try:
        response = requests.get(url, headers=headers, stream=True, timeout=30)

        if response.status_code != 200:
            print(f"🚨 requests 跨域搬运握手失败，CDN 状态码: {response.status_code}")
            raise HTTPException(status_code=response.status_code, detail=f"目标直链响应异常，状态码: {response.status_code}")

        def chunk_generator():
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk

        content_type = response.headers.get("Content-Type", "application/octet-stream")
        filename = "file.mp4" if "video" in content_type.lower() else "image.jpg"

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