# 文件名: main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import httpx
import uuid  # 引入 Python 自带的 UUID 库，用来生成绝对不重复的短 ID

# 1. 初始化 FastAPI 应用
app = FastAPI(title="SnapDownloader ID Mapping Backend")

# 2. 开启全量 CORS 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 【核心升级 1】建立全局内存下载缓存字典
# 它的结构会是：{"短ID": {"url": "真实CDN链接", "headers": {原装请求头字典}}}
DOWNLOAD_CACHE = {}

# 健康检查接口
@app.get("/")
@app.get("/api/v1/health")
async def health_check():
    # 顺便在健康检查里打印一下当前缓存了多少个任务，方便观察
    return {
        "status": "ok", 
        "message": "内存映射流式下载服务运行中",
        "cached_tasks_count": len(DOWNLOAD_CACHE)
    }


# 4. 智能提取接口（负责解析并存入“钥匙”）
@app.post("/api/v1/extract")
async def extract_stream(request: Request):
    try:
        # 直接读取前端发送的裸文本（text/plain）请求体
        raw_body = await request.body()
        url_input = raw_body.decode("utf-8").strip()
        
        print(f"========================================")
        print(f"📡 收到前端裸文本解析请求: {url_input}")
        print(f"========================================")
        
        if not url_input:
            raise HTTPException(status_code=400, detail="输入的视频网址不能为空")
            
        # 配置 yt-dlp 核心参数
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
            # 用 yt-dlp 进行网络嗅探
            info = ydl.extract_info(url_input, download=False)
            
            title = info.get('title', '未命名原流视频')
            
            # 提取最高清封面
            cover = info.get('thumbnail')
            if not cover and info.get('thumbnails'):
                cover = info['thumbnails'][-1].get('url')
            if not cover:
                cover = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500"
                
            # 提取真实的视频原流直链
            video_url = info.get('url')
            target_format = None
            if not video_url and info.get('formats'):
                valid_formats = [f for f in info['formats'] if f.get('url')]
                if valid_formats:
                    target_format = valid_formats[-1]
                    video_url = target_format.get('url')
                    
            if not video_url:
                raise Exception("无法从该页面中提取出有效的原音频/视频无水印直链地址")
                
            # 计算文件大小
            filesize = info.get('filesize') or info.get('filesize_approx')
            if not filesize and target_format:
                filesize = target_format.get('filesize') or target_format.get('filesize_approx')
                
            size_str = f"{filesize / (1024 * 1024):.1f} MB" if filesize else "高清原流"
            
            # --- 【核心升级 2】掏出原装钥匙（HTTP Headers） ---
            # 优先获取顶层的请求头
            original_headers = info.get('http_headers', {})
            # 如果顶层没有，则去具体选中的高清格式(format)字典里掏原装请求头（TikTok、小红书非常喜欢藏在这里）
            if not original_headers and target_format:
                original_headers = target_format.get('http_headers', {})
            
            # 确保原装钥匙里有一个兜底的 User-Agent，防止部分平台漏掉
            if 'User-Agent' not in original_headers and 'user-agent' not in original_headers:
                original_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

            # --- 【核心升级 3】生成唯一的 task_id 并存入全局缓存 ---
            task_id = str(uuid.uuid4())[:12]  # 生成一个 12 位长、绝对不重复的精简安全 ID
            DOWNLOAD_CACHE[task_id] = {
                "url": video_url,
                "headers": original_headers
            }
            
            print(f"🔑 钥匙打包成功！生成临时映射 ID: {task_id}")
            print(f"📦 当前原装请求头包含: {list(original_headers.keys())}")
            
            # --- 【核心升级 4】动态拼接只带 ID 参数的精简中转链接 ---
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
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 解析服务崩溃，异常原因: {error_msg}")
        raise HTTPException(status_code=500, detail=f"解析失败: {error_msg}")


# 5. 【核心升级 5】全新重写的 ID 中转下载接口
@app.get("/api/v1/download")
async def proxy_download(id: str):
    # 检查前端有没有传 id 过来
    if not id:
        raise HTTPException(status_code=400, detail="缺少必要的 id 参数")
        
    # 从全局字典中寻找这把钥匙。如果没有，说明链接过期了，或者服务器重启了
    if id not in DOWNLOAD_CACHE:
        print(f"🚨 找不到对应的映射 ID: {id}，可能已被释放或请求非法。")
        raise HTTPException(status_code=404, detail="下载任务已失效，请重新回前端解析链接")
        
    # 完好无损地把对应的真实 URL 和那套原装 HTTP 请求头取出来
    task_data = DOWNLOAD_CACHE[id]
    video_url = task_data["url"]
    original_headers = task_data["headers"]
    
    print(f"📥 成功提取钥匙 {id}！开始流式搬运目标 CDN 资源...")
    
    # 显式手动声明异步客户端，接管连接生命周期
    client = httpx.AsyncClient(follow_redirects=True)
    try:
        # 【核心升级 6】全量喂入原装 http_headers 钥匙，完美攻破防盗链！
        req = client.build_request("GET", video_url, headers=original_headers)
        response = await client.send(req, stream=True)
        
        # 前置状态码检查（非 200 强力阻断）
        if response.status_code != 200:
            print(f"🚨 CDN 携密握手依旧失败！对方返回状态码: {response.status_code}")
            await response.aclose()
            await client.aclose()
            raise HTTPException(
                status_code=response.status_code, 
                detail=f"目标 CDN 拒绝了原装钥匙中转，状态码: {response.status_code}"
            )
            
    except HTTPException:
        raise
    except Exception as network_err:
        print(f"🚨 建立网络长连接时发生未知故障: {network_err}")
        await client.aclose()
        raise HTTPException(status_code=500, detail=f"后端中转握手失败: {str(network_err)}")

    print(f"✅ 携密验证通过 (HTTP 200 OK)，开始源源不断地输送无损二进制流...")

    # 流式迭代器，确保稳定传输与长连接闭合
    async def stream_generator():
        try:
            async for chunk in response.aiter_bytes(chunk_size=65536):
                yield chunk
        except Exception as stream_err:
            print(f"⚠️ 传输中途流发生中断: {stream_err}")
        finally:
            # 传输完毕、中途取消均百分之百强制关闭并释放内存资源
            await response.aclose()
            await client.aclose()
            print(f"🔒 [安全闭合] 映射任务 {id} 的所有网络长连接已成功释放。")

    # 强制触发浏览器弹出保存文件框，拒绝在线播放
    return StreamingResponse(
        stream_generator(),
        media_type="video/mp4",
        headers={
            "Content-Disposition": "attachment; filename=video.mp4"
        }
    )