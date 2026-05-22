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


# 3. 核心接口：双引擎盲测开放纯直链提取接口
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
        
        # 探测是否为推特/X或IG等具备高密混合媒体潜力的国际大厂平台
        is_international_mix_platform = any(domain in cleaned_url.lower() for domain in ["twitter.com", "x.com", "instagram.com"])
        
        # 🚀 【核心重构逻辑】：双引擎智能盲测分流
        try:
            # 【分流策略修正】：如果遇到了明显的推特/X或IG混合帖子，优先直接滑向全新的 yt-dlp 全能雷达扫描
            # 这样可以确保单次会话中，视频直链和被遗漏的多张照片能在一个作用域里被全量合并捞回
            if is_international_mix_platform:
                raise ValueError("检测到推特/IG大厂混合媒体潜能链接，强制启动 yt-dlp 终极雷达合并扫描")

            # Step A: 盲测第一步，其余常规平台默认扔给 gallery-dl 底层引擎
            extractor = gallery_dl.extractor.find(cleaned_url)
            if extractor is None:
                raise ValueError("gallery-dl 盲测未匹配，转交二次防御视频流引擎")
            
            gallery_config.load()
            gallery_config.set(("output",), "mode", "url") 
            if current_cookie_path:
                gallery_config.set(("extractor",), "cookies", current_cookie_path)
                
            print(f"📸 [双引擎分流] gallery-dl 拦截成功！正在执行模拟无损直链剥离...")
            
            capture_stream = io.StringIO()
            with contextlib.redirect_stdout(capture_stream):
                job = gallery_job.DataJob(cleaned_url)
                job.run()
                
            output_lines = capture_stream.getvalue().splitlines()
            for line in output_lines:
                clean_line = line.strip()
                if clean_line.startswith("http://") or clean_line.startswith("https://"):
                    is_video_file = any(ext in clean_line.lower() for ext in [".mp4", ".m3u8", ".mov", ".webm"])
                    media_list.append({
                        "type": "video" if is_video_file else "image",
                        "url": clean_line
                    })
            
            if not media_list:
                raise ValueError("gallery-dl 模拟提取未见有效图集直链")
            print(f"🎯 [gallery-dl 成功] 成功提取出 {len(media_list)} 个直链对象")

        except Exception as gallery_err:
            # Step B: gallery-dl 探测未通过（或被推特混合策略强制挂起），全自动转交给 yt-dlp 视频流引擎接管
            print(f"ℹ️ 分流引导切入二次防御网：yt-dlp 视频流引擎。原因: {gallery_err}")
            
            # 🚀 【核心修复点一】：强制指定格式过滤，拦截 m3u8，索要真实 MP4 纯净直链
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,      # 核心：纯直链模式大门全开不落盘
                'extract_flat': False,
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # 强制限定 MP4 基因组合
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web_creator'] # 手机端欺骗伪装
                    }
                }
            }
            if current_cookie_path:
                ydl_opts['cookiefile'] = current_cookie_path
                
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(cleaned_url, download=False)
                
                # 安全阻断过滤清洗器：双重检查，宁可漏掉，也绝不放过任何包含 .m3u8 或 manifest 的伪造直链
                def clean_progressive_url(raw_url: str) -> str:
                    if not raw_url:
                        return ""
                    url_check = raw_url.lower()
                    if ".m3u8" in url_check or "manifest" in url_check:
                        return ""  # 强制粉碎恶意 m3u8 切片索引
                    return raw_url

                # 提取视频直链的核心函数（深度从 formats 基因库里筛选出绝对纯净的单文件 mp4 真实直链）
                def resolve_pure_mp4_url(item_data) -> str:
                    # 1. 尝试外层直接提供的链接
                    direct_url = clean_progressive_url(item_data.get('url'))
                    if direct_url:
                        return direct_url
                    
                    # 2. 如果外层为空或外层被确认为 m3u8，则去 formats 格式列表中检索完全符合 mp4 封装的实体直链
                    formats = item_data.get('formats', [])
                    valid_mp4_formats = [
                        f for f in formats 
                        if f.get('url') and f.get('ext') == 'mp4' and not any(x in f.get('url').lower() for x in ['.m3u8', 'manifest'])
                    ]
                    
                    if valid_mp4_formats:
                        # 优先寻找已经合并好了音频和视频的常规直链 (vcodec和acodec均不为none)
                        combined = [f for f in valid_mp4_formats if f.get('vcodec') != 'none' and f.get('acodec') != 'none']
                        if combined:
                            return combined[-1].get('url')
                        return valid_mp4_formats[-1].get('url') # 拿画质最高的一款
                    
                    # 3. 终极无条件兜底：寻找格式库里任何不包含 m3u8 字样的非空直链
                    any_progressive = [f for f in formats if f.get('url') and not any(x in f.get('url').lower() for x in ['.m3u8', 'manifest'])]
                    if any_progressive:
                        return any_progressive[-1].get('url')
                        
                    return ""

                # 🚀 【核心修复点二】：全量捞回混合帖子指纹图片函数
                def collect_mixed_media_thumbnails(item_data):
                    thumbnails = item_data.get('thumbnails', [])
                    for t in thumbnails:
                        t_url = t.get('url', '')
                        # 锁定大厂大图特征网址特征字段进行精准清洗过滤
                        if t_url and any(keyword in t_url for keyword in ['pbs.twimg.com/media/', 'twimg.com/media/', 'instagram.com/p/']):
                            # 剔除重复的推特大图缩略图干扰项（有些不同分辨率会重定向到同一张图片）
                            base_media_url = t_url.split('?')[0] if '?' in t_url else t_url
                            if not any(base_media_url in m['url'] for m in media_list):
                                media_list.append({
                                    "type": "image",
                                    "url": t_url
                                })

                # 场景一：多媒体/播放列表格式解析环 (Entries 存在)
                if 'entries' in info and info['entries']:
                    for entry in info['entries']:
                        if not entry: continue
                        v_url = resolve_pure_mp4_url(entry)
                        if v_url:
                            media_list.append({"type": "video", "url": v_url})
                        
                        # 强行同步捕获当前 entry 下被遗漏的所有多图特写
                        collect_mixed_media_thumbnails(entry)
                        
                # 场景二：常规单贴或混合帖子主作用域解析环
                else:
                    v_url = resolve_pure_mp4_url(info)
                    if v_url:
                        media_list.append({"type": "video", "url": v_url})
                    
                    # 强行同步捕获当前主贴下被遗漏的所有多图特写（1视频+2图片的经典推特结构会在这里一网打尽）
                    collect_mixed_media_thumbnails(info)
            
            if not media_list:
                raise Exception("双引擎盲测链条均未能从该网址中提取到任何不含 m3u8 的高清实体直链地址")
            print(f"🎯 [yt-dlp 成功] 成功捞回并合并了 {len(media_list)} 个无损流媒体纯净直链")

        # 🚀 【核心点三】：严格对齐并升级你给出的全新 JSON 返回响应体规范格式
        return {
            "code": 200,
            "msg": "success",
            "data": media_list
        }
            
    except HTTPException:
        raise
    except Exception as e:
        error_msg_raw = str(e)
        error_msg_lower = error_msg_raw.lower()
        print(f"❌ 路由器双链路彻底断裂，原因: {error_msg_raw}")
        
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


# 4. 🚀 【核心点五】：完美保留并升级的免受 CORS 跨域防盗链困扰的 proxy-download 代理中转接口
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
        # 实时流式读取，彻底封死 m3u8，requests 在面对纯 progressive 实体 MP4 链接时会健壮地以 chunk 形式搬运
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        
        if response.status_code != 200:
            print(f"🚨 requests 跨域搬运握手失败，CDN 状态码: {response.status_code}")
            raise HTTPException(status_code=response.status_code, detail=f"目标直链响应异常，状态码: {response.status_code}")
            
        # 纯内存实时缓冲 64KB 片段下发，服务器硬盘占用率绝对保持为 0%
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