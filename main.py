# 文件名: main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

# 1. 初始化 FastAPI 应用
app = FastAPI(title="SnapDownloader Production Backend")

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
    return {"status": "ok", "message": "视频流解析后端服务正在运行中..."}

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
            
        # 配置 yt-dlp 核心参数（加入了针对 YouTube 的常规反爬拦截与防封锁伪装）
        ydl_opts = {
            'quiet': True,            # 禁止打印多余的运行时调试日志
            'no_warnings': True,      # 忽略非致命警告
            'skip_download': True,    # 核心：只抓取元数据，绝不下载视频到服务器本地
            'extract_flat': False,    # 深度提取流媒体真实的直链地址
            
            # 【防封锁升级 1】注入标准桌面端浏览器请求头，防止被识别为无头脚本
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
            },
            
            # 【防封锁升级 2】核心突破口：伪装 YouTube 访问客户端
            # 强制让 yt-dlp 放弃使用默认容易被拦截的网页客户端，转而模拟 ios、android 手机端和网页内嵌播放器
            # 这通常能绕过绝大多数对云服务器机房 IP 实施的 "Sign in to confirm you're not a bot" 限制
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android', 'web_embedded']
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 开始调用库进行真实网页嗅探与解析
            info = ydl.extract_info(url_input, download=False)
            
            # 1. 提取真实视频标题
            title = info.get('title', '未命名原流视频')
            
            # 2. 提取最高清封面图网址
            cover = info.get('thumbnail')
            if not cover and info.get('thumbnails'):
                cover = info['thumbnails'][-1].get('url')  # 尝试获取列表中分辨率最高的封面
            if not cover:
                cover = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500"  # 兜底默认图
                
            # 3. 提取真实的视频原流直链下载链接
            video_url = info.get('url')
            if not video_url and info.get('formats'):
                # 如果外层没有直接提供 url，则去 formats 格式列表中筛选出有效的直链
                valid_formats = [f for f in info['formats'] if f.get('url')]
                if valid_formats:
                    # 过滤并尝试选择同时包含音频和视频的完整流（或者排序最后的优质流）
                    video_url = valid_formats[-1].get('url')
                    
            if not video_url:
                raise Exception("无法从该页面中提取出有效的原音频/视频无水印直链地址")
                
            # 4. 计算或预估真实文件大小
            filesize = info.get('filesize') or info.get('filesize_approx')
            if filesize:
                size_str = f"{filesize / (1024 * 1024):.1f} MB"
            else:
                size_str = "高清原流"
                
            # 5. 严格返回完全适配前端渲染组件的 JSON 数据结构
            return {
                "type": "video",
                "title": title,
                "size": size_str,
                "cover": cover,
                "actions": [
                    { "type": "primary", "label": "🟢 高速无损下载", "url": video_url }
                ]
            }
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 解析服务崩溃，异常原因: {error_msg}")
        # 发生错误时拦截并返回 500 状态码，透传错误信息，完美触发前端的异常弹窗拦截组件
        raise HTTPException(status_code=500, detail=f"解析失败: {error_msg}")