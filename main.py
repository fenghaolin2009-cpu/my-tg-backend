# 文件名: main.py
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import yt_dlp
import uuid
import os
import tempfile  # 智能引入跨域临时目录库，完美适配 Windows 本地和 Linux/Render 云端

# 1. 初始化 FastAPI 应用
app = FastAPI(title="SnapDownloader Burning-After-Reading Backend")

# 2. 开启全量 CORS 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 全局内存下载缓存字典
# 结构变更为：{"短ID": {"original_url": "用户提交的原始分享链接"}}
DOWNLOAD_CACHE = {}


# 后台清理函数：在文件成功下发给前端后，由 BackgroundTasks 异步调用，执行“阅后即焚”
def cleanup_file(file_path: str):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ [阅后即焚] 临时视频文件已被安全、彻底地从硬盘删除: {file_path}")
    except Exception as cleanup_err:
        print(f"❌ [阅后即焚] 清理临时文件失败: {cleanup_err}")


# 健康检查接口
@app.get("/")
@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "ok", 
        "message": "暂存区物理流式中转服务正常运行中...",
        "active_tasks": len(DOWNLOAD_CACHE)
    }


# 4. 智能提取接口（负责秒级提取元数据，并登记原始链接任务）
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
            
        # 配置 yt-dlp 快速嗅探参数（只拿元数据，不下载视频）
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
            
            # 提取最高清封面
            cover = info.get('thumbnail')
            if not cover and info.get('thumbnails'):
                cover = info['thumbnails'][-1].get('url')
            if not cover:
                cover = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=500"
                
            # 计算预估文件大小
            filesize = info.get('filesize') or info.get('filesize_approx')
            size_str = f"{filesize / (1024 * 1024):.1f} MB" if filesize else "高清原流"
            
            # --- 【核心策略修改】这里缓存用户提交的“原始网页链接” ---
            # 只有让中转接口拿到原始链接，yt-dlp 才能带上完整独立的 Cookie 状态突破 TikTok 封锁
            task_id = str(uuid.uuid4())[:12]
            DOWNLOAD_CACHE[task_id] = {
                "original_url": url_input
            }
            
            print(f"🔑 任务登记成功！临时映射 ID: {task_id}")
            
            # 动态拼接精简的中转链接
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


# 5. 【终极防御】同步中转下载接口
# 注意：这里去掉了 async 关键字，声明为普通的同步 def 函数。
# FastAPI 探测到同步函数后，会自动将其丢进独立的外部线程池运行，确保 yt-dlp 本地下载时绝对不会卡死主线程！
@app.get("/api/v1/download")
def proxy_download(id: str, background_tasks: BackgroundTasks):
    if not id:
        raise HTTPException(status_code=400, detail="缺少必要的 id 参数")
        
    if id not in DOWNLOAD_CACHE:
        raise HTTPException(status_code=404, detail="下载任务已失效或服务器已重启，请回前端重新解析")
        
    # 取出原始链接
    original_url = DOWNLOAD_CACHE[id]["original_url"]
    print(f"🚀 [物理落盘启动] 正在调用 yt-dlp 将资源下载至服务器暂存区: {original_url}")
    
    # 智能化定位临时目录（Windows 上是 Temp，Render/Linux 上是 /tmp）
    temp_dir = tempfile.gettempdir()
    file_name = f"snap_{uuid.uuid4()}.mp4"
    file_path = os.path.join(temp_dir, file_name)
    
    # 配置 yt-dlp 真实物理下载参数
    ydl_opts = {
        'outtmpl': file_path,     # 指定物理落盘路径
        # 【超级避坑指南】格式必须指定为 'best'（单文件最高清）。
        # 绝不能写 'bestvideo+bestaudio'，因为合并音视频强依赖服务器必须安装 ffmpeg 软件。
        # 选择 'best' 可以确保在没有 ffmpeg 的基础 Render 服务器上直接成功输出完整的 MP4 文件！
        'format': 'best',         
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        }
    }
    
    try:
        # 在独立的线程池中安全执行物理下载
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([original_url])
            
        # 严密检查文件是否真的下载成功并落盘
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            raise Exception("yt-dlp 下载引擎未能成功在服务器生成有效的实体文件")
            
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        print(f"🟢 物理暂存大成功！文件大小: {file_size_mb:.2f} MB，路径: {file_path}")
        
        # 【核心升级】注册“阅后即焚”后台清理任务
        # 当下面的 FileResponse 把文件全量输送给前端浏览器完毕后，FastAPI 会自动触发 cleanup_file 把它扬了
        background_tasks.add_task(cleanup_file, file_path)
        
        # 使用 FileResponse 执行无损大物理文件下发，强制触发浏览器“保存文件”弹窗
        return FileResponse(
            path=file_path,
            media_type="video/mp4",
            filename="video.mp4"  # 告诉前端浏览器保存时的默认名字
        )
        
    except Exception as e:
        error_msg = str(e)
        print(f"🚨 服务器本地中转发生致命崩溃: {error_msg}")
        # 出错兜底：如果有残留的半成品残渣文件，顺手清理掉防止塞满硬盘
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        raise HTTPException(status_code=500, detail=f"后端实体暂存失败: {error_msg}")