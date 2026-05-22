# 文件名: main.py
import asyncio
from contextlib import asynccontextmanager
import os
import re
import tempfile
import uuid
from typing import AsyncGenerator, Dict, List, Any, Optional
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx
import yt_dlp

# --- 全局特征映射配置表 ---
COOKIE_MAPPING: Dict[str, str] = {
    "instagram.com": "IG_COOKIE_TEXT",
    "twitter.com": "TWITTER_COOKIE_TEXT",
    "x.com": "TWITTER_COOKIE_TEXT",
    "youtube.com": "YOUTUBE_COOKIE_TEXT",
    "youtu.be": "YOUTUBE_COOKIE_TEXT"
}

REFERER_MAPPING: Dict[str, str] = {
    "tiktok.com": "https://www.tiktok.com/",
    "instagram.com": "https://www.instagram.com/",
    "twitter.com": "https://x.com/",
    "x.com": "https://x.com/",
    "twimg.com": "https://x.com/"
}

# --- 模块顶级作用域工具函数 (优化编译内耗) ---
def clean_progressive_url(raw_url: str) -> str:
    """过滤含有分块切片特征的非实体直链"""
    return "" if not raw_url or any(x in raw_url.lower() for x in [".m3u8", "manifest"]) else raw_url

def resolve_pure_mp4_url(item_data: Dict[str, Any]) -> str:
    """从媒体特征数据集中提取纯净的实体 MP4 直链"""
    if direct := clean_progressive_url(item_data.get('url', '')):
        return direct
    
    valid_mp4s = [
        f for f in item_data.get('formats', []) 
        if f.get('url') and f.get('ext') == 'mp4' and not any(x in f.get('url', '').lower() for x in ['.m3u8', 'manifest'])
    ]
    if valid_mp4s:
        combined = [f for f in valid_mp4s if f.get('vcodec') != 'none' and f.get('acodec') != 'none']
        return combined[-1].get('url', '') if combined else valid_mp4s[-1].get('url', '')
        
    progressives = [
        f for f in item_data.get('formats', []) 
        if f.get('url') and not any(x in f.get('url', '').lower() for x in ['.m3u8', 'manifest'])
    ]
    return progressives[-1].get('url', '') if progressives else ""

def collect_thumbnails_safe(
    item_data: Dict[str, Any], 
    media_list: List[Dict[str, str]], 
    yt_dlp_images: List[Dict[str, str]], 
    seen_yt_imgs: set
) -> None:
    """深度过滤提取缩略图节点中归属大厂特征的独立图片资产"""
    for t in item_data.get('thumbnails', []):
        if (t_url := t.get('url', '')) and any(k in t_url for k in ['pbs.twimg.com/media/', 'twimg.com/media/', 'instagram.com/p/']):
            if t_url not in seen_yt_imgs and not any(t_url in m['url'] for m in media_list):
                seen_yt_imgs.add(t_url)
                yt_dlp_images.append({"type": "image", "url": t_url})

def utils_extract_clean_url(dirty_text: str) -> str:
    """提取纯净的网际协议请求链接"""
    match = re.search(r"https?://[^\s]+", dirty_text)
    return match.group(0) if match else ""

def utils_create_temp_cookie_file(url: str) -> str:
    """基于环境变量及域名特征动态创建短期验证凭证"""
    env_key = next((v for k, v in COOKIE_MAPPING.items() if k in url.lower()), "")
    cookie_text = os.getenv(env_key, "") if env_key else ""
    if cookie_text.strip():
        try:
            cookie_path = os.path.join(tempfile.gettempdir(), f"cookie_auth_{uuid.uuid4()}.txt")
            with open(cookie_path, "w", encoding="utf-8") as f:
                f.write(cookie_text.strip())
            return cookie_path
        except Exception as e:
            print(f"⚠️ 动态生成临时 Cookie 失败: {e}")
    return ""

def utils_safe_remove_cookie_file(cookie_path: str) -> None:
    """清除由于鉴权产生的本地临时离盘文件"""
    if cookie_path and os.path.exists(cookie_path):
        try:
            os.remove(cookie_path)
            print(f"🔒 [安全释放] 临时验证 Cookie 凭证已从磁盘销毁: {cookie_path}")
        except Exception as e:
            print(f"❌ 销毁临时 Cookie 失败: {e}")

def sync_yt_dlp_extract(target_url: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """同步阻塞执行的核心数据提取层"""
    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(target_url, download=False)

# --- 异步全局连接池生命周期托管 ---
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # 初始化全局异步非阻塞 HTTP 客户端，控制连接池复用上限
    app.state.client = httpx.AsyncClient(limits=httpx.Limits(max_connections=200, max_keepalive_connections=50))
    yield
    # 应用关闭阶段优雅清退并注销所有底层 Socket 长连接
    await app.state.client.aclose()

app = FastAPI(title="SnapDownloader Pure-Link Anti-M3U8 Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
@app.get("/api/v1/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok", "message": "全球流媒体开放网关全量平稳运行中..."}

@app.post("/api/v1/extract")
async def extract_stream(request: Request) -> Dict[str, Any]:
    current_cookie_path: str = ""
    process: Optional[asyncio.subprocess.Process] = None
    try:
        dirty_input = (await request.body()).decode("utf-8").strip()
        cleaned_url = utils_extract_clean_url(dirty_input)
        
        if not cleaned_url or not cleaned_url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="未检测到合法的 http:// 或 https:// 视频或图集链接")

        # 完美匹配不区分大小写的域名清洗与归整规整
        if re.search(r"x\.com", cleaned_url, flags=re.IGNORECASE):
            cleaned_url = re.sub(r"x\.com", "twitter.com", cleaned_url, flags=re.IGNORECASE)
            print(f"🔄 [域名洗白] 完美清洗混合大小写 X 域名特征，已将其精准替换为 twitter.com")

        current_cookie_path = utils_create_temp_cookie_file(cleaned_url)
        media_list: List[Dict[str, str]] = []
        is_youtube = any(yt_domain in cleaned_url.lower() for yt_domain in ["youtube.com", "youtu.be"])

        # ============================================================
        # 【阶段一：资产初筛搜刮 (异步非阻塞子进程管道通信)】
        # ============================================================
        if not is_youtube:
            try:
                cmd = ["gallery-dl", "-g", cleaned_url]
                if current_cookie_path:
                    cmd.extend(["--cookies", current_cookie_path])
                
                print(f"📸 [阶段一] 启动异步非阻塞子进程调用 gallery-dl")
                process = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=30.0)
                
                # 退出状态码精确强校验
                if process.returncode != 0:
                    print(f"ℹ️ gallery-dl 进程触发异常退出码 {process.returncode}: {stderr_bytes.decode('utf-8', errors='ignore')}")
                else:
                    for line in stdout_bytes.decode("utf-8", errors="ignore").splitlines():
                        if (c := line.strip()).startswith(("http://", "https://")):
                            is_video = any(ext in c.lower() for ext in [".mp4", ".m3u8", ".mov", ".webm"])
                            media_list.append({"type": "video" if is_video else "image", "url": c})
                print(f"🎯 [阶段一完成] 异步管道内核成功捕获到 {len(media_list)} 个原始资产节点")
            except asyncio.TimeoutError:
                # 操作系统级子进程树生命周期强行规整回收
                print("🚨 [安全熔断] gallery-dl 超时触发强力拦截！正在操作系统层面清理挂起的子进程。")
                if process and process.returncode is None:
                    process.kill()
                    await process.wait()
            except Exception as gallery_err:
                print(f"ℹ️ [阶段一提示] gallery-dl 管道建立失败或发生未知异常: {gallery_err}")
                if process and process.returncode is None:
                    process.kill()
                    await process.wait()

        # ============================================================
        # 【阶段二：高清视频重构升级与资产无损交叉合并 (yt-dlp)】
        # ============================================================
        has_video_clue = any(m["type"] == "video" for m in media_list)
        is_major_platform = is_youtube or any(domain in cleaned_url.lower() for domain in ["twitter.com", "instagram.com"])

        if not media_list or has_video_clue or is_major_platform:
            print(f"🔄 [阶段二] 触发重构协同判定，正在唤醒隔离线程池中的 yt-dlp 雷达...")
            ydl_opts: Dict[str, Any] = {
                'quiet': True, 'no_warnings': True, 'skip_download': True, 'extract_flat': False,
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'web_creator', 'mweb', 'tv']}}
            }
            
            # 环境提权参数加密级指纹映射装配
            po_val, vis_val = os.getenv("YOUTUBE_PO_TOKEN", ""), os.getenv("YOUTUBE_VISITOR_DATA", "")
            if po_val: ydl_opts['extractor_args']['youtube']['po_token'] = [f'web+{po_val}', f'android+{po_val}']
            if vis_val: ydl_opts['extractor_args']['youtube']['visitor_data'] = vis_val
            if current_cookie_path: ydl_opts['cookiefile'] = current_cookie_path

            try:
                # 托管同步长网络 I/O 运行于子线程，防范主事件循环阻塞
                info = await asyncio.to_thread(sync_yt_dlp_extract, cleaned_url, ydl_opts)

                yt_dlp_images: List[Dict[str, str]] = []
                seen_yt_imgs = set()
                
                # 调用模型顶级命名空间的提取单元
                yt_dlp_videos: List[Dict[str, str]] = []
                if 'entries' in info and info['entries']:
                    for entry in info['entries']:
                        if entry:
                            if v_url := resolve_pure_mp4_url(entry): yt_dlp_videos.append({"type": "video", "url": v_url})
                            collect_thumbnails_safe(entry, media_list, yt_dlp_images, seen_yt_imgs)
                else:
                    if v_url := resolve_pure_mp4_url(info): yt_dlp_videos.append({"type": "video", "url": v_url})
                    collect_thumbnails_safe(info, media_list, yt_dlp_images, seen_yt_imgs)

                # 智能交叉去重合并算法，防止因重构失败导致视频数据降级死锁
                retained_images = [m for m in media_list if m["type"] == "image"]
                gallery_videos = [m for m in media_list if m["type"] == "video"]
                final_videos = yt_dlp_videos if yt_dlp_videos else gallery_videos
                media_list = retained_images + yt_dlp_images + final_videos
                print(f"⚡ [无损智能拼装] 留存大图 {len(retained_images)} 个，雷达大图 {len(yt_dlp_images)} 个，合并视频 {len(final_videos)} 个")
            
            except Exception as ytdlp_err:
                err_msg_str = str(ytdlp_err).lower()
                if "confirm you're not a bot" in err_msg_str or "sign in to confirm" in err_msg_str:
                    print(f"🚨 [风控阻断] 拦截到强力登录墙验证，强透传强抛激活！")
                    raise ytdlp_err
                print(f"ℹ️ [阶段二提示] yt-dlp 线程隔离流遭遇非致命异常: {ytdlp_err}")

        # ==========================================
        # 【阶段三：最终收网与安全去重】
        # ==========================================
        seen_urls = set()
        final_media_list: List[Dict[str, str]] = []
        for item in media_list:
            url = item["url"]
            if not any(x in url.lower() for x in [".m3u8", "manifest"]) and url not in seen_urls:
                seen_urls.add(url)
                final_media_list.append(item)

        if not final_media_list:
            raise Exception("双引擎异步协同流水线运行完毕，未能提取到任何有效的图片资产或纯净实体视频直链")

        return {"code": 200, "msg": "success", "data": final_media_list}

    except HTTPException:
        raise
    except Exception as e:
        error_msg_lower = str(e).lower()
        print(f"❌ 异步流水线断裂，异常详情: {e}")
        if "cookies" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🚨 当前海外服务器 IP 被大厂风控拦截，请稍后再试，或检查后端 Cookie 变量配置。")
        if "confirm you're not a bot" in error_msg_lower or "sign in to confirm" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🚨 YouTube 触发了最强机器人登录墙验证！请立即检查并更新 Render 后台的环境变量。")
        if "twitter" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🔒 推特 (X) 官方触发了匿名访问限制，请在后台配置对应的验证 Cookie。")
        if "instagram" in error_msg_lower and "no video" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🔒 Instagram 访问请求被官方安全验证墙拦截，请更换 Cookie 或稍后再试。")
        raise HTTPException(status_code=500, detail=f"流媒体直链网关提取失败: {e}")
    finally:
        if current_cookie_path:
            utils_safe_remove_cookie_file(current_cookie_path)


# ============================================================================================
# 【完美生命周期闭环：高性能异步 HTTP Range 传输隧道 (通过 BackgroundTasks 确保资源物理自销毁)】
# ============================================================================================
@app.get("/api/v1/proxy-download")
async def proxy_download(url: str, request: Request, background_tasks: BackgroundTasks) -> StreamingResponse:
    if not url:
        raise HTTPException(status_code=400, detail="缺少必要的 url 参数")

    # 单行高效静态查表，重构业务防盗链引荐来源欺骗
    referer = next((v for k, v in REFERER_MAPPING.items() if k in url.lower()), "https://google.com")
    headers: Dict[str, str] = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": referer}

    if client_range := request.headers.get("Range"):
        headers["Range"] = client_range
        print(f"🚀 [Async Range] 成功透传前端分块头: {client_range}")

    # 获取全局常驻的唯一复用流网络套接字客户端
    client: httpx.AsyncClient = request.app.state.client
    try:
        req = client.build_request("GET", url, headers=headers)
        response = await client.send(req, stream=True, timeout=30.0)

        if response.status_code not in [200, 206]:
            await response.aclose()
            raise HTTPException(status_code=response.status_code, detail=f"目标直链 CDN 响应异常: {response.status_code}")

        # 还原分块流特征下发包头参数
        out_headers: Dict[str, str] = {
            "Content-Disposition": f"attachment; filename={'file.mp4' if 'video' in response.headers.get('Content-Type', '').lower() else 'image.jpg'}",
            "Accept-Ranges": response.headers.get("Accept-Ranges", "bytes")
        }
        for h in ["Content-Range", "Content-Length"]:
            if h in response.headers: 
                out_headers[h] = response.headers[h]

        # 将关闭网络流任务注入后台异步任务中，确保网关在完全推送二进制数据碎片后安全闭环
        background_tasks.add_task(response.aclose)
        print("🔒 [后台流注销就绪] 异步传输生命周期已注册到 BackgroundTasks，保障物理自销毁安全路径。")

        return StreamingResponse(
            response.aiter_bytes(chunk_size=65536),
            status_code=response.status_code,
            media_type=response.headers.get("Content-Type", "application/octet-stream"),
            headers=out_headers
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"🚨 异步代购中转网络层崩溃: {e}")
        raise HTTPException(status_code=500, detail=f"后端免跨域流式非阻塞中转失败: {e}")