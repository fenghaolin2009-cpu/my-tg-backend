# 文件名: main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from urllib.parse import quote
import yt_dlp
import httpx

# 1. 初始化 FastAPI 应用
app = FastAPI(title="SnapDownloader Ultra Robust Backend")

# 2. 开启全量 CORS 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 健康检查接口
@app.get("/")
@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "message": "高容错中转下载服务正在全量防御运行中..."}


# 4. 真实原流提取接口
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
            info = ydl.extract_info(url_input, download=False)
            
            title = info.get('title', '未命名原流视频')
            
            cover = info.get('thumbnail')
            if not cover and info.get('thumbnails'):
                cover = info['thumbnails'][-1].get('url')
            if not cover:
                cover = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500"
                
            video_url = info.get('url')
            if not video_url and info.get('formats'):
                valid_formats = [f for f in info['formats'] if f.get('url')]
                if valid_formats:
                    video_url = valid_formats[-1].get('url')
                    
            if not video_url:
                raise Exception("无法从该页面中提取出有效的原音频/视频无水印直链地址")
                
            filesize = info.get('filesize') or info.get('filesize_approx')
            if filesize:
                size_str = f"{filesize / (1024 * 1024):.1f} MB"
            else:
                size_str = "高清原流"
                
            # 动态拼接后端代理下载链接
            base_url = str(request.base_url).rstrip('/')
            encoded_video_url = quote(video_url, safe='')
            proxy_download_url = f"{base_url}/api/v1/download?url={encoded_video_url}"
            
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


# 5. 地狱级容错：反向代理流式中转下载接口
@app.get("/api/v1/download")
async def proxy_download(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="缺少必要的 url 参数")
        
    print(f"📥 后端接管网络流，开始请求真实 CDN: {url[:60]}...")
    
    # 【核心升级 1】注入完美伪装头，全面攻破 TikTok 针对机房 IP 的防盗链保护
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://www.tiktok.com/',   # 必须伪装成 TikTok 内部来源
        'Accept': '*/*',
        'Accept-Encoding': 'identity',           # 确保 CDN 传输原始文件，禁止压缩破坏
    }
    
    # 显式手动声明客户端，接管连接生命周期，彻底杜绝因为代码 return 导致提前闭合产生 0B 的 Bug
    client = httpx.AsyncClient(follow_redirects=True)
    try:
        # 构建流式长连接请求
        req = client.build_request("GET", url, headers=headers)
        response = await client.send(req, stream=True)
        
        # 【核心升级 2】前置状态码拦截。在数据发送给前端之前进行强力体检
        if response.status_code != 200:
            print(f"🚨 CDN 握手失败！对方返回状态码: {response.status_code}。正在强制阻断空流！")
            # 发现异常立即闭合，绝不拖泥带水
            await response.aclose()
            await client.aclose()
            # 直接抛出标准的 HTTP 异常错误，让前端能够精准捕捉到拦截原因
            raise HTTPException(
                status_code=response.status_code, 
                detail=f"TikTok CDN 拒绝了中转请求，状态码: {response.status_code}。请尝试重新解析新链接。"
            )
            
    except HTTPException:
        # 如果是状态码检查不通过的 HTTPException，直接往上抛出，让前端弹窗
        raise
    except Exception as network_err:
        # 捕捉其他网络握手超时或连接失败等致命故障
        print(f"🚨 与目标 CDN 建立连接时发生网络层崩溃: {network_err}")
        await client.aclose()
        raise HTTPException(status_code=500, detail=f"后端中转握手失败: {str(network_err)}")

    print(f"✅ CDN 验证通过 (HTTP 200 OK)，开始流式安全搬运无损字节流...")

    # 【核心升级 3】确保流式迭代器正确闭合的生成器函数
    async def stream_generator():
        try:
            # 持续从小块中实时读取，稳稳当当地输送视频流碎片
            async for chunk in response.aiter_bytes(chunk_size=65536):
                yield chunk
        except Exception as stream_err:
            print(f"⚠️ 搬运字节流时，前端中途掐断或连接异常: {stream_err}")
        finally:
            # 无论是前端下载完成、中途主动取消、还是网络发生中断，
            # 最终（finally）都百分之百强制关闭底层的 response 和 client 连接，释放内存资源
            await response.aclose()
            await client.aclose()
            print(f"🔒 [安全闭合] 该长连接对应的所有中转网络流已全量释放回收。")

    # 4. 强制触发浏览器弹出保存文件框，拒绝在线播放
    return StreamingResponse(
        stream_generator(),
        media_type="video/mp4",
        headers={
            "Content-Disposition": "attachment; filename=video.mp4"
        }
    )