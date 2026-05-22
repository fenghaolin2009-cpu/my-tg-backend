# 文件名: main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import gallery_dl
from gallery_dl import config as gallery_config, job as gallery_job
import requests
import uuid
import os
import re
import tempfile
import io
import contextlib

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


# 工具函数 2：根据网址从环境变量动态生成临时 Cookie 文件（后备隐藏防线）
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


# 3. 核心接口：双引擎协同串联流水线提取接口
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

        # 激活隐藏 Cookie 物理生成
        current_cookie_path = utils_create_temp_cookie_file(cleaned_url)

        # 统一准备装载解析结果的数组
        media_list = []

        # ==========================================
        # 【阶段一：资产初筛搜刮 (gallery-dl)】
        # ==========================================
        extractor = gallery_dl.extractor.find(cleaned_url)
        if extractor is not None:
            try:
                gallery_config.load()
                gallery_config.set(("output",), "mode", "url")
                if current_cookie_path:
                    gallery_config.set(("extractor",), "cookies", current_cookie_path)

                print(f"📸 [阶段一] gallery-dl 匹配成功！正在执行全量资产初步搜刮...")

                capture_stream = io.StringIO()
                with contextlib.redirect_stdout(capture_stream):
                    job = gallery_job.DataJob(cleaned_url)
                    job.run()

                output_lines = capture_stream.getvalue().splitlines()
                for line in output_lines:
                    clean_line = line.strip()
                    if clean_line.startswith("http://") or clean_line.startswith("https://"):
                        # 初步判断是否为视频特征扩展名
                        is_video_file = any(ext in clean_line.lower() for ext in [".mp4", ".m3u8", ".mov", ".webm"])
                        media_list.append({
                            "type": "video" if is_video_file else "image",
                            "url": clean_line
                        })
                print(f"🎯 [阶段一完成] gallery-dl 搜刮到 {len(media_list)} 个基础资产节点")
            except Exception as gallery_err:
                # 阶段一遇到异常时不中断，允许滑入阶段二兜底或由其深度捕获
                print(f"ℹ️ [阶段一提示] gallery-dl 解析遭遇非致命异常: {gallery_err}")

        # ==========================================
        # 【阶段二：高清视频重构（基因升级）(yt-dlp)】
        # ==========================================
        has_video = any(m["type"] == "video" for m in media_list)
        is_major_platform = any(domain in cleaned_url.lower() for domain in ["twitter.com", "x.com", "instagram.com"])

        # 触发判定条件：①资产库为空；②库中含有视频线索；③属于大厂混合平台
        if not media_list or has_video or is_major_platform:
            print(f"🔄 [阶段二] 触发重构协同判定，正在唤醒 yt-dlp 终极雷达进行高清视频捕获...")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,      # 纯直链模式大门全开不落盘
                'extract_flat': False,
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # 强制限定 MP4 组合
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web_creator'] # 手机端欺骗伪装，穿透机房限制
                    }
                }
            }
            if current_cookie_path:
                ydl_opts['cookiefile'] = current_cookie_path

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(cleaned_url, download=False)

            # 安全阻断过滤清洗器：强力粉碎恶意 m3u8 / manifest 切片索引文本
            def clean_progressive_url(raw_url: str) -> str:
                if not raw_url:
                    return ""
                url_check = raw_url.lower()
                if ".m3u8" in url_check or "manifest" in url_check:
                    return ""
                return raw_url

            # 深度从 formats 基因库里筛选出绝对纯净的单文件 mp4 真实直链
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

            # 专属提取 yt-dlp 侧重构的高清视频列表
            yt_dlp_videos = []
            if 'entries' in info and info['entries']:
                for entry in info['entries']:
                    if not entry: continue
                    v_url = resolve_pure_mp4_url(entry)
                    if v_url:
                        yt_dlp_videos.append({"type": "video", "url": v_url})
            else:
                v_url = resolve_pure_mp4_url(info)
                if v_url:
                    yt_dlp_videos.append({"type": "video", "url": v_url})

            # 【关键替换逻辑】：如果 yt-dlp 成功捕获到了高清无损的视频直链
            if yt_dlp_videos:
                # 绝不动摇阶段一捞出来的 image 节点，仅精准抹除旧的 video 节点
                media_list = [m for m in media_list if m["type"] != "video"]
                # 将基因升级后的纯净视频直链无缝并入
                media_list.extend(yt_dlp_videos)
                print(f"⚡ [重构成功] 已成功用 yt-dlp 高清 MP4 节点替换了可能存在画质瑕疵的旧视频流")

        # ==========================================
        # 【阶段三：最终收网与去重】
        # ==========================================
        seen_urls = set()
        final_media_list = []
        for item in media_list:
            url = item["url"]
            url_lower = url.lower()
            
            # 最后的马奇诺防线：任何渠道残留的恶意 m3u8 / manifest 链接一律不予放行
            if ".m3u8" in url_lower or "manifest" in url_lower:
                continue
                
            if url not in seen_urls:
                seen_urls.add(url)
                final_media_list.append(item)

        if not final_media_list:
            raise Exception("双引擎协同流水线均未能从该网址中提取到任何不含 m3u8 的高清实体直链地址")

        print(f"🎯 [流水线收网] 最终完美合并去重，共计输出 {len(final_media_list)} 个直链资产对象")
        
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
        print(f"❌ 协同流水线彻底断裂，原因: {error_msg_raw}")

        # 高情商风控中文降级提示
        if "cookies" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🚨 当前海外服务器 IP 被平台风控拦截，请稍后再试或更换其他平台链接（如 TikTok/B站）。")
        if "twitter" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🔒 推特 (X) 官方触发了海外公共机房 IP 匿名访问限制，请稍后重试。")
        if "instagram" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🔒 本次 Instagram 访问请求被官方安全验证拦截，请更换其他链接或稍后再试。")

        raise HTTPException(status_code=500, detail=f"全球流媒体开放网关直链提取失败，请检查链接可达性: {error_msg_raw}")
    finally:
        if current_cookie_path:
            utils_safe_remove_cookie_file(current_cookie_path)


# 4. 免受 CORS 跨域防盗链困扰的 proxy-download 代理中转接口（保持原样，未做任何修改）
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
        # 实时流式长连接二进制分块搬运
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