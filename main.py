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

# 1. 初始化纯净的 FastAPI 应用 [cite: 76]
app = FastAPI(title="SnapDownloader Pure-Link Anti-M3U8 Backend") [cite: 77]

# 2. 开启全量 CORS 跨域配置 [cite: 78, 79]
app.add_middleware(
    CORSMiddleware, [cite: 80]
    allow_origins=["*"], [cite: 81]
    allow_credentials=True, [cite: 82]
    allow_methods=["*"], [cite: 83]
    allow_headers=["*"], [cite: 84]
)


# 工具函数 1：正则表达式清洗过滤文本口令（剥离出纯净网址） [cite: 86]
def utils_extract_clean_url(dirty_text: str) -> str: [cite: 87]
    match = re.search(r"https?://[^\s]+", dirty_text) [cite: 88]
    if match: [cite: 89]
        return match.group(0) [cite: 90]
    return "" [cite: 91]


# ------------------------------------------------------------
# 【修复指标一：扩容临时 Cookie 拦截雷达，全面并入 YouTube 凭证感知】
# ------------------------------------------------------------
def utils_create_temp_cookie_file(url: str) -> str: [cite: 92]
    url_lower = url.lower() [cite: 94]
    cookie_text = "" [cite: 95]
    if "instagram.com" in url_lower: [cite: 96]
        cookie_text = os.getenv("IG_COOKIE_TEXT", "") [cite: 97]
    elif "twitter.com" in url_lower or "x.com" in url_lower: [cite: 98]
        cookie_text = os.getenv("TWITTER_COOKIE_TEXT", "") [cite: 99]
    # 强力追加判定：拦截 YouTube 域名，无缝衔接 Render 后台环境变量 [cite: 324]
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        cookie_text = os.getenv("YOUTUBE_COOKIE_TEXT", "")

    if cookie_text.strip(): [cite: 100]
        try: [cite: 101]
            temp_dir = tempfile.gettempdir() [cite: 102]
            cookie_filename = f"cookie_auth_{uuid.uuid4()}.txt" [cite: 103]
            cookie_path = os.path.join(temp_dir, cookie_filename) [cite: 104]
            with open(cookie_path, "w", encoding="utf-8") as f: [cite: 105]
                f.write(cookie_text.strip()) [cite: 106]
            return cookie_path [cite: 107]
        except Exception as e: [cite: 108]
            print(f"⚠️ 动态生成临时 Cookie 失败: {e}") [cite: 109]
            return "" [cite: 110]
    return ""


# 工具函数 3：强力就地销毁临时 Cookie 凭证 [cite: 111, 112]
def utils_safe_remove_cookie_file(cookie_path: str): [cite: 112]
    if cookie_path and os.path.exists(cookie_path): [cite: 113]
        try: [cite: 114]
            os.remove(cookie_path) [cite: 115]
            print(f"🔒 [安全释放] 临时验证 Cookie 凭证已从磁盘销毁: {cookie_path}") [cite: 116]
        except Exception as e: [cite: 117]
            print(f"❌ 销毁临时 Cookie 失败: {e}") [cite: 118]


# 健康检查接口 [cite: 119]
@app.get("/") [cite: 120]
@app.get("/api/v1/health") [cite: 121]
async def health_check(): [cite: 122]
    return {"status": "ok", "message": "终结 2KB 骗子文件！全球流媒体开放网关全量平稳运行中..."} [cite: 123]


# 3. 核心接口：双引擎串联协同无损流水线提取接口 [cite: 124, 125]
@app.post("/api/v1/extract") [cite: 125]
async def extract_stream(request: Request): [cite: 126]
    current_cookie_path = "" [cite: 127]
    try: [cite: 128]
        raw_body = await request.body() [cite: 129]
        dirty_input = raw_body.decode("utf-8").strip() [cite: 130]

        print(f"========================================") [cite: 131]
        print(f"📥 开放直链网关收到文本请求: {dirty_input[:100]}...") [cite: 132]
        print(f"========================================") [cite: 133]

        cleaned_url = utils_extract_clean_url(dirty_input) [cite: 134]
        if not cleaned_url or not (cleaned_url.startswith("http://") or cleaned_url.startswith("https://")): [cite: 135]
            raise HTTPException(status_code=400, detail="未检测到合法的 http:// 或 https:// 视频或图集链接") [cite: 136]

        # 【洗白模块】：保持对大厂域名的强行清洗与统一规范
        if "x.com" in cleaned_url.lower():
            cleaned_url = cleaned_url.replace("x.com", "twitter.com").replace("X.com", "twitter.com")
            print(f"🔄 [域名洗白] 检测到 x.com 域名，已强行修正替换为 twitter.com 以激活核心解析器规则")

        print(f"✨ 网关清洗后送入流水线的最终 URL: {cleaned_url}") [cite: 137]

        # 激活隐藏 Cookie 物理生成 [cite: 138, 139]
        current_cookie_path = utils_create_temp_cookie_file(cleaned_url)

        # 统一准备装载解析结果的数组 [cite: 140, 141]
        media_list = []

        # ==========================================
        # 【阶段一：资产初筛搜刮 (工业级系统管道版)】
        # ==========================================
        try:
            # 建立物理隔离进程，-g 参数原生纯文本无损吐出 URL
            cmd = ["gallery-dl", "-g", cleaned_url]
            if current_cookie_path and not any(yt_domain in cleaned_url.lower() for yt_domain in ["youtube.com", "youtu.be"]):
                cmd.extend(["--cookies", current_cookie_path])

            # 仅在非 YouTube 链接时尝试走第一阶段命令流搜刮图集 [cite: 33]
            if not any(yt_domain in cleaned_url.lower() for yt_domain in ["youtube.com", "youtu.be"]):
                print(f"📸 [阶段一] 启动系统级进程调用 gallery-dl CLI: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
                
                output_lines = result.stdout.splitlines()
                for line in output_lines:
                    clean_line = line.strip()
                    if clean_line.startswith("http://") or clean_line.startswith("https://"): [cite: 165]
                        is_video_file = any(ext in clean_line.lower() for ext in [".mp4", ".m3u8", ".mov", ".webm"]) [cite: 166]
                        media_list.append({ [cite: 167]
                            "type": "video" if is_video_file else "image", [cite: 168]
                            "url": clean_line [cite: 169]
                        }) [cite: 170]
                print(f"🎯 [阶段一完成] 进程内核成功捕获到 {len(media_list)} 个原始资产节点")
        except Exception as gallery_err:
            print(f"ℹ️ [阶段一提示] gallery-dl 核心流处理跳过或遭遇风控，交由二次防御网兜底: {gallery_err}") [cite: 176]

        # ==========================================
        # 【阶段二：高清视频重构升级与资产无损合并 (yt-dlp)】 [cite: 175]
        # ==========================================
        has_video_clue = any(m["type"] == "video" for m in media_list)
        is_major_platform = any(domain in cleaned_url.lower() for domain in ["twitter.com", "instagram.com", "youtube.com", "youtu.be"])

        if not media_list or has_video_clue or is_major_platform:
            print(f"🔄 [阶段二] 触发重构协同判定，正在唤醒 yt-dlp 终极雷达进行高清视频捕获...")
            
            # ------------------------------------------------------------
            # 【修复指标二：全量升级 yt-dlp 伪装客户端基因库，物理穿透机房风控墙】
            # ------------------------------------------------------------
            ydl_opts = { [cite: 178]
                'quiet': True, [cite: 179]
                'no_warnings': True, [cite: 180]
                'skip_download': True,      # 纯直链模式大门全开不落盘 [cite: 181]
                'extract_flat': False, [cite: 182]
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # 强制限定 MP4 组合 [cite: 183]
                'http_headers': { [cite: 184]
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36', [cite: 185]
                }, [cite: 186]
                'extractor_args': { [cite: 187]
                    'youtube': { [cite: 188]
                        # 补齐具有极高机房风控豁免权的全客户端欺骗阵列，无缝穿透机器人验证限制 
                        'player_client': ['android', 'ios', 'web_creator', 'mweb', 'tv']
                    } [cite: 190]
                } [cite: 191]
            } [cite: 192]
            
            if current_cookie_path: [cite: 193]
                ydl_opts['cookiefile'] = current_cookie_path [cite: 194]

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl: [cite: 195]
                    info = ydl.extract_info(cleaned_url, download=False) [cite: 196]

                # 安全阻断过滤清洗器：强力粉碎恶意 m3u8 / manifest 切片索引文本 [cite: 197]
                def clean_progressive_url(raw_url: str) -> str: [cite: 198]
                    if not raw_url: [cite: 199]
                        return "" [cite: 200]
                    url_check = raw_url.lower() [cite: 201]
                    if ".m3u8" in url_check or "manifest" in url_check: [cite: 202]
                        return "" [cite: 203]
                    return raw_url [cite: 204]

                # 从 formats 基因库里筛选出绝对纯净的单文件 mp4 真实直链 [cite: 205]
                def resolve_pure_mp4_url(item_data) -> str: [cite: 206]
                    direct_url = clean_progressive_url(item_data.get('url')) [cite: 207]
                    if direct_url: [cite: 208]
                        return direct_url [cite: 209]

                    formats = item_data.get('formats', []) [cite: 210]
                    valid_mp4_formats = [ [cite: 211]
                        f for f in formats [cite: 212]
                        if f.get('url') and f.get('ext') == 'mp4' and not any(x in f.get('url').lower() for x in ['.m3u8', 'manifest']) [cite: 213]
                    ] [cite: 214]
                    if valid_mp4_formats: [cite: 215]
                        combined = [f for f in valid_mp4_formats if f.get('vcodec') != 'none' and f.get('acodec') != 'none'] [cite: 216]
                        if combined: [cite: 217]
                            return combined[-1].get('url') [cite: 218]
                        return valid_mp4_formats[-1].get('url') [cite: 219]

                    any_progressive = [f for f in formats if f.get('url') and not any(x in f.get('url').lower() for x in ['.m3u8', 'manifest'])] [cite: 220]
                    if any_progressive: [cite: 221]
                        return any_progressive[-1].get('url') [cite: 222]
                    return "" [cite: 223]

                # 捞回潜在的混合神贴大图指纹资产 [cite: 35]
                yt_dlp_images = []
                def collect_thumbnails_safe(item_data): [cite: 225]
                    thumbnails = item_data.get('thumbnails', []) [cite: 226]
                    for t in thumbnails: [cite: 227]
                        t_url = t.get('url', '') [cite: 228]
                        if t_url and any(keyword in t_url for keyword in ['pbs.twimg.com/media/', 'twimg.com/media/', 'instagram.com/p/']): [cite: 229]
                            if not any(t_url in m['url'] for m in media_list): [cite: 231]
                                yt_dlp_images.append({"type": "image", "url": t_url}) [cite: 232]

                yt_dlp_videos = []
                if 'entries' in info and info['entries']: [cite: 236, 237]
                    for entry in info['entries']: [cite: 238]
                        if not entry: continue [cite: 239]
                        v_url = resolve_pure_mp4_url(entry) [cite: 240]
                        if v_url: [cite: 241]
                            yt_dlp_videos.append({"type": "video", "url": v_url}) [cite: 242]
                        collect_thumbnails_safe(entry) [cite: 243]
                else: [cite: 245]
                    v_url = resolve_pure_mp4_url(info) [cite: 246]
                    if v_url: [cite: 247]
                        yt_dlp_videos.append({"type": "video", "url": v_url}) [cite: 248]
                    collect_thumbnails_safe(info) [cite: 249]

                # 【无损合并守则】：死死扣住第一阶段 subprocess 捕获的所有图片，合并第二阶段升级的高清视频
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
            
            # 【铁律】：任何渠道残留的恶意 m3u8 / manifest 文本索引切片一律抹除 [cite: 34, 335]
            if ".m3u8" in url_lower or "manifest" in url_lower:
                continue
                
            if url not in seen_urls:
                seen_urls.add(url)
                final_media_list.append(item)

        if not final_media_list: [cite: 250]
            raise Exception("双引擎串联协同流水线运行完毕，未能提取到任何有效的图片资产或纯净实体视频直链") [cite: 251]

        print(f"🎯 [流水线收网] 最终资产去重清洗完成，共计输出 {len(final_media_list)} 个直链资产对象") [cite: 252]
        
        return { [cite: 253]
            "code": 200, [cite: 255]
            "msg": "success", [cite: 256]
            "data": final_media_list [cite: 257]
        } [cite: 258]

    except HTTPException: [cite: 259]
        raise [cite: 260]
    except Exception as e: [cite: 261]
        error_msg_raw = str(e) [cite: 262]
        error_msg_lower = error_msg_raw.lower() [cite: 263]
        print(f"❌ 协同流水线彻底断裂，异常详情: {error_msg_raw}") [cite: 264]

        # 高情商风控中文提示透传 [cite: 46, 265]
        if "cookies" in error_msg_lower: [cite: 266]
            raise HTTPException(status_code=400, detail="🚨 当前海外服务器 IP 被大厂风控拦截，请稍后再试，或检查后端相应平台的 Cookie 变量配置。") [cite: 267]
        if "confirm you're not a bot" in error_msg_lower or "sign in to confirm" in error_msg_lower:
            raise HTTPException(status_code=400, detail="🚨 YouTube 触发了最强机器人登录墙验证！请立即检查并更新 Render 后台的 YOUTUBE_COOKIE_TEXT 环境变量。")
        if "twitter" in error_msg_lower and "no video" in error_msg_lower: [cite: 268]
            raise HTTPException(status_code=400, detail="🔒 推特 (X) 官方触发了匿名访问限制，请在 VPS / Render 配置对应的验证 Cookie。") [cite: 269]
        if "instagram" in error_msg_lower and "no video" in error_msg_lower: [cite: 270]
            raise HTTPException(status_code=400, detail="🔒 Instagram 访问请求被官方安全验证墙拦截，请稍后再试或更新 Cookie。") [cite: 271]

        raise HTTPException(status_code=500, detail=f"流媒体直链网关提取失败，请检查目标链接状态: {error_msg_raw}") [cite: 272]
    finally: [cite: 273]
        if current_cookie_path: [cite: 274]
            utils_safe_remove_cookie_file(current_cookie_path) [cite: 275]


# 4. 免受 CORS 跨域防盗链困扰的 proxy-download 代理中转接口（保持原样，未做任何简化篡改） [cite: 47, 276, 277]
@app.get("/api/v1/proxy-download") [cite: 277]
def proxy_download(url: str): [cite: 278]
    if not url: [cite: 279]
        raise HTTPException(status_code=400, detail="缺少必要的 url 参数") [cite: 280]

    print(f"📥 requests 跨域中转网关接管，正在搬运实时流...") [cite: 281]

    headers = { [cite: 282]
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36', [cite: 283]
    } [cite: 284]

    url_lower = url.lower() [cite: 285]
    if "tiktok.com" in url_lower: [cite: 286]
        headers["Referer"] = "https://www.tiktok.com/" [cite: 287]
    elif "instagram.com" in url_lower: [cite: 288]
        headers["Referer"] = "https://www.instagram.com/" [cite: 289]
    elif "twitter.com" in url_lower or "x.com" in url_lower or "twimg.com" in url_lower: [cite: 290]
        headers["Referer"] = "https://x.com/" [cite: 291]

    try: [cite: 292]
        # 实时流式长连接二进制分块搬运 [cite: 51, 293]
        response = requests.get(url, headers=headers, stream=True, timeout=30) [cite: 294]

        if response.status_code != 200: [cite: 295]
            print(f"🚨 requests 跨域搬运握手失败，CDN 状态码: {response.status_code}") [cite: 296]
            raise HTTPException(status_code=response.status_code, detail=f"目标直链响应异常，状态码: {response.status_code}") [cite: 297]

        def chunk_generator(): [cite: 298]
            for chunk in response.iter_content(chunk_size=65536): [cite: 299]
                if chunk: [cite: 300]
                    yield chunk [cite: 301]

        content_type = response.headers.get("Content-Type", "application/octet-stream") [cite: 302]
        filename = "file.mp4" if "video" in content_type.lower() else "image.jpg" [cite: 303]

        return StreamingResponse( [cite: 304]
            chunk_generator(), [cite: 305]
            media_type=content_type, [cite: 306]
            headers={ [cite: 307]
                "Content-Disposition": f"attachment; filename={filename}" [cite: 308]
            } [cite: 309]
        ) [cite: 310]

    except HTTPException: [cite: 311]
        raise [cite: 312]
    except Exception as e: [cite: 313]
        print(f"🚨 中转代理网络层发生不可逆崩溃: {e}") [cite: 314]
        raise HTTPException(status_code=500, detail=f"后端免跨域流式中转失败: {str(e)}") [cite: 315]