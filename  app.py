from config_manager import load_config, save_config

# بارگذاری یا ساخت کانفیگ
config = load_config()

if not config:
    print("🔧 Welcome! Let's set up your Telegram API configuration.")
    api_id = input("Enter your Telegram API_ID: ")
    api_hash = input("Enter your Telegram API_HASH: ")
    phone = input("Enter your PHONE number: ")

    save_config(api_id, api_hash, phone)
    config = load_config()
    print("✅ Config saved successfully!\n")

API_ID = config["API_ID"]
API_HASH = config["API_HASH"]
PHONE = config["PHONE"]




# # تنظیمات تلگرام
# API_ID = '732757'
# API_HASH = '9572884801dd15dcbb4ae2104ee26573'
# PHONE = '+971569161834'

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.functions.channels import JoinChannelRequest
import asyncio
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
from pathlib import Path



if not all([API_ID, API_HASH, PHONE]):
    raise ValueError("❌ لطفاً API_ID, API_HASH و PHONE را در .env تنظیم کنید")

# ساخت FastAPI app
app = FastAPI(
    title="Telegram RSS Generator API",
    description="Generate RSS feeds from Telegram channels with media support",
    version="2.0.0"
)

# ساخت فولدر برای ذخیره عکس‌ها
MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)

# Serve کردن فایل‌های static
app.mount("/media", StaticFiles(directory="media"), name="media")

# کلاینت تلگرام
client = None

@app.on_event("startup")
async def startup_event():
    """راه‌اندازی کلاینت تلگرام"""
    global client
    client = TelegramClient('session_name', API_ID, API_HASH)
    await client.start(phone=PHONE)
    print("✅ کلاینت تلگرام متصل شد")

@app.on_event("shutdown")
async def shutdown_event():
    """قطع ارتباط کلاینت"""
    global client
    if client:
        await client.disconnect()
        print("🔌 کلاینت تلگرام قطع شد")

async def get_channel_messages(channel_link: str, limit: int = 50):
    """دریافت پیام‌های کانال با اطلاعات media"""
    try:
        # اگر عدد صحیح یا شروع با - باشه، مستقیم به عنوان Channel ID استفاده کن
        if channel_link.lstrip('-').isdigit():
            channel_id = int(channel_link)
            entity = await client.get_entity(channel_id)
        else:
            # برای کانال‌های پرایوت اگر invite link هست، اول join کن
            if 'joinchat/' in channel_link or '/+' in channel_link:
                try:
                    await client(JoinChannelRequest(channel_link))
                    print(f"✅ به کانال پرایوت join شد: {channel_link}")
                except Exception as join_error:
                    print(f"ℹ️  Join info: {join_error}")
            
            entity = await client.get_entity(channel_link)
        
        # دریافت پیام‌ها با batch برای limit های بالا
        all_messages = []
        offset_id = 0
        
        # برای limit بالاتر از 100، چند بار درخواست می‌زنیم
        remaining = limit
        while remaining > 0:
            batch_size = min(remaining, 100)  # Telethon حداکثر 100 تا میده
            
            messages = await client(GetHistoryRequest(
                peer=entity,
                limit=batch_size,
                offset_date=None,
                offset_id=offset_id,
                max_id=0,
                min_id=0,
                add_offset=0,
                hash=0
            ))
            
            if not messages.messages:
                break  # دیگه پیامی نیست
            
            all_messages.extend(messages.messages)
            
            # آخرین message id رو برای offset بعدی نگه می‌داریم
            offset_id = messages.messages[-1].id
            remaining -= len(messages.messages)
            
            # اگه کمتر از batch_size اومد، یعنی تموم شده
            if len(messages.messages) < batch_size:
                break
        
        # استخراج اطلاعات media از هر پیام
        messages_with_media = []
        for msg in all_messages:
            media_files = []
            
            # چک کردن انواع media
            if msg.photo:
                # عکس تکی
                media_files.append({
                    'type': 'photo',
                    'id': msg.photo.id,
                    'access_hash': msg.photo.access_hash,
                    'file_reference': msg.photo.file_reference.hex()
                })
            elif msg.media and hasattr(msg.media, 'webpage') and hasattr(msg.media.webpage, 'photo'):
                # عکس در webpage
                photo = msg.media.webpage.photo
                if photo:
                    media_files.append({
                        'type': 'photo',
                        'id': photo.id,
                        'access_hash': photo.access_hash,
                        'file_reference': photo.file_reference.hex()
                    })
            elif hasattr(msg, 'media') and hasattr(msg.media, 'document'):
                # فایل یا ویدیو
                doc = msg.media.document
                mime_type = doc.mime_type if hasattr(doc, 'mime_type') else 'unknown'
                if mime_type.startswith('image/'):
                    media_files.append({
                        'type': 'document',
                        'id': doc.id,
                        'access_hash': doc.access_hash,
                        'file_reference': doc.file_reference.hex(),
                        'mime_type': mime_type
                    })
            
            # اگر پیام گروهی از media داره (آلبوم)
            if hasattr(msg, 'grouped_id') and msg.grouped_id:
                # این پیام جزو یک آلبوم عکسه
                msg.is_album = True
                msg.grouped_id_value = msg.grouped_id
            else:
                msg.is_album = False
            
            msg.media_files = media_files
            messages_with_media.append(msg)
        
        return entity, messages_with_media
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"خطا در دریافت پیام‌ها: {str(e)}")

def group_album_messages(messages, limit=None):
    """گروه‌بندی پیام‌های آلبومی (چند عکس در یک پست)"""
    grouped = {}
    singles = []
    
    for msg in messages:
        if hasattr(msg, 'grouped_id') and msg.grouped_id:
            # این پیام جزو یک آلبومه
            if msg.grouped_id not in grouped:
                grouped[msg.grouped_id] = {
                    'messages': [],
                    'first_msg': msg
                }
            grouped[msg.grouped_id]['messages'].append(msg)
        else:
            # پیام تکی
            singles.append(msg)
    
    # ترکیب پیام‌های گروهی
    result = []
    
    for group_id, group_data in grouped.items():
        # اولین پیام رو به عنوان پیام اصلی استفاده می‌کنیم
        main_msg = group_data['first_msg']
        
        # همه media های گروه رو جمع می‌کنیم
        all_media = []
        all_texts = []
        
        for msg in group_data['messages']:
            all_media.extend(msg.media_files)
            # اگه پیام متن داشت، اضافه کن
            if msg.message:
                all_texts.append(msg.message)
        
        # ترکیب متن‌ها (معمولاً فقط یکی متن داره)
        if all_texts:
            main_msg.message = '\n\n'.join(all_texts)
        
        main_msg.media_files = all_media
        main_msg.is_album = True
        main_msg.album_count = len(group_data['messages'])
        result.append(main_msg)
    
    # اضافه کردن پیام‌های تکی
    result.extend(singles)
    
    # مرتب‌سازی بر اساس تاریخ
    result.sort(key=lambda x: x.date if x.date else datetime.min, reverse=True)
    
    # اعمال limit بعد از گروه‌بندی (اگه داده شده باشه)
    if limit:
        result = result[:limit]
    
    return result

def create_rss_feed(channel_info, messages, channel_link, base_url, original_limit):
    """ساخت فید RSS"""
    # گروه‌بندی پیام‌های آلبومی با اعمال limit بعد از گروه‌بندی
    messages = group_album_messages(messages, limit=original_limit)
    
    rss = ET.Element('rss', version='2.0', attrib={
        'xmlns:atom': 'http://www.w3.org/2005/Atom',
        'xmlns:media': 'http://search.yahoo.com/mrss/'
    })
    channel = ET.SubElement(rss, 'channel')
    
    title = ET.SubElement(channel, 'title')
    title.text = channel_info.title
    
    link = ET.SubElement(channel, 'link')
    link.text = f"https://t.me/{channel_info.username}" if channel_info.username else channel_link
    
    description = ET.SubElement(channel, 'description')
    description.text = channel_info.title or "Telegram Channel RSS Feed"
    
    last_build = ET.SubElement(channel, 'lastBuildDate')
    last_build.text = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    for msg in messages:
        if msg.message or msg.media_files:
            item = ET.SubElement(channel, 'item')
            
            item_title = ET.SubElement(item, 'title')
            if msg.message:
                msg_text = msg.message[:100] + '...' if len(msg.message) > 100 else msg.message
            else:
                msg_text = f"Media Post ({len(msg.media_files)} files)"
            item_title.text = msg_text
            
            item_link = ET.SubElement(item, 'link')
            if channel_info.username:
                item_link.text = f"https://t.me/{channel_info.username}/{msg.id}"
            else:
                item_link.text = f"https://t.me/c/{channel_info.id}/{msg.id}"
            
            # توضیحات با عکس‌ها
            item_desc = ET.SubElement(item, 'description')
            desc_content = ""
            
            # اضافه کردن عکس‌ها
            for idx, media in enumerate(msg.media_files):
                media_url = f"{base_url}/download/{channel_info.id}/{msg.id}/{media['id']}"
                desc_content += f'<img src="{media_url}" alt="Image {idx+1}" style="max-width:100%; margin:5px;"/>'
            
            if desc_content:
                desc_content += '<br/><br/>'
            
            if msg.message:
                desc_content += msg.message
            
            item_desc.text = f"<![CDATA[{desc_content}]]>"
            
            # اضافه کردن media:group برای چند عکس
            if msg.media_files:
                media_group = ET.SubElement(item, '{http://search.yahoo.com/mrss/}group')
                for media in msg.media_files:
                    media_url = f"{base_url}/download/{channel_info.id}/{msg.id}/{media['id']}"
                    media_content = ET.SubElement(media_group, '{http://search.yahoo.com/mrss/}content')
                    media_content.set('url', media_url)
                    media_content.set('type', 'image/jpeg')
                    media_content.set('medium', 'image')
            
            pub_date = ET.SubElement(item, 'pubDate')
            if msg.date:
                pub_date.text = msg.date.strftime('%a, %d %b %Y %H:%M:%S +0000')
            
            guid = ET.SubElement(item, 'guid', isPermaLink='true')
            guid.text = item_link.text
    
    xml_str = minidom.parseString(ET.tostring(rss, encoding='utf-8')).toprettyxml(indent='  ', encoding='utf-8').decode('utf-8')
    return xml_str

@app.get("/")
async def root():
    """صفحه اصلی API"""
    return {
        "name": "Telegram RSS Generator API",
        "version": "2.0.0",
        "endpoints": {
            "/rss": "دریافت RSS فید",
            "/json": "دریافت JSON",
            "/download/{channel_id}/{msg_id}/{media_id}": "دانلود عکس",
            "/health": "وضعیت سرویس",
            "/docs": "مستندات کامل API"
        },
        "examples": {
            "rss": "/rss?channel=@durov&limit=20",
            "json": "/json?channel=-1001234567890&limit=10",
            "download": "/download/-1001234567890/12345/9876543210"
        }
    }

@app.get("/health")
async def health_check():
    """بررسی سلامت"""
    is_connected = client and client.is_connected()
    return {
        "status": "healthy" if is_connected else "unhealthy",
        "telegram_connected": is_connected,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/rss")
async def get_rss(channel: str, limit: int = 50):
    """
    دریافت RSS فید
    
    - **channel**: لینک، یوزرنیم یا ID کانال
      - پابلیک: @channel یا https://t.me/channel
      - پرایوت (invite link): https://t.me/+XXXXX
      - پرایوت (عضو هستید): -1001234567890
    - **limit**: تعداد پست‌ها (بعد از گروه‌بندی آلبوم‌ها)
    """
    if not client or not client.is_connected():
        raise HTTPException(status_code=503, detail="سرویس در دسترس نیست")
    
    # برای گرفتن limit پست، ممکنه نیاز باشه پیام‌های بیشتری بگیریم
    # چون ممکنه آلبوم‌ها چند پیام باشن
    fetch_limit = min(limit * 3, 1000)  # حداکثر 1000 پیام
    
    channel_info, messages = await get_channel_messages(channel, fetch_limit)
    
    # ساخت base URL برای لینک‌های media
    base_url = "http://localhost:8000"  # این رو باید از request header بگیری در production
    
    rss_content = create_rss_feed(channel_info, messages, channel, base_url, limit)
    
    return Response(content=rss_content, media_type="application/xml")

@app.get("/json")
async def get_json(channel: str, limit: int = 50):
    """
    دریافت JSON
    
    - **channel**: لینک، یوزرنیم یا ID
    - **limit**: تعداد پست‌ها (بعد از گروه‌بندی)
    """
    if not client or not client.is_connected():
        raise HTTPException(status_code=503, detail="سرویس در دسترس نیست")
    
    # برای گرفتن limit پست، ممکنه نیاز باشه پیام‌های بیشتری بگیریم
    fetch_limit = min(limit * 3, 1000)
    
    channel_info, messages = await get_channel_messages(channel, fetch_limit)
    
    # گروه‌بندی پیام‌های آلبومی
    messages = group_album_messages(messages, limit=limit)
    
    result = {
        "channel": {
            "id": channel_info.id,
            "title": channel_info.title,
            "username": channel_info.username,
        },
        "messages": [
            {
                "id": msg.id,
                "text": msg.message,
                "date": msg.date.isoformat() if msg.date else None,
                "views": msg.views,
                "link": f"https://t.me/{channel_info.username}/{msg.id}" if channel_info.username else f"https://t.me/c/{channel_info.id}/{msg.id}",
                "is_album": msg.is_album if hasattr(msg, 'is_album') else False,
                "album_count": msg.album_count if hasattr(msg, 'album_count') else 1,
                "media": [
                    {
                        "type": m['type'],
                        "id": m['id'],
                        "download_url": f"/download/{channel_info.id}/{msg.id}/{m['id']}"
                    }
                    for m in msg.media_files
                ] if msg.media_files else []
            }
            for msg in messages if msg.message or msg.media_files
        ],
        "total": len([m for m in messages if m.message or m.media_files])
    }
    
    return result

@app.get("/download/{channel_id}/{msg_id}/{media_id}")
async def download_media(channel_id: int, msg_id: int, media_id: int):
    """
    دانلود یک عکس خاص
    
    - **channel_id**: ID کانال
    - **msg_id**: ID پیام
    - **media_id**: ID فایل media
    """
    if not client or not client.is_connected():
        raise HTTPException(status_code=503, detail="سرویس در دسترس نیست")
    
    try:
        # چک کردن اگه قبلاً دانلود شده
        file_path = MEDIA_DIR / f"{channel_id}_{msg_id}_{media_id}.jpg"
        
        if file_path.exists():
            return FileResponse(file_path, media_type="image/jpeg")
        
        # دریافت پیام و دانلود media
        entity = await client.get_entity(channel_id)
        message = await client.get_messages(entity, ids=msg_id)
        
        if not message:
            raise HTTPException(status_code=404, detail="پیام پیدا نشد")
        
        # دانلود media
        if message.photo:
            downloaded_path = await client.download_media(message.photo, file=str(file_path))
        elif message.media and hasattr(message.media, 'document'):
            downloaded_path = await client.download_media(message.media.document, file=str(file_path))
        else:
            raise HTTPException(status_code=404, detail="این پیام media ندارد")
        
        if not downloaded_path:
            raise HTTPException(status_code=500, detail="خطا در دانلود فایل")
        
        return FileResponse(file_path, media_type="image/jpeg")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطا در دانلود media: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)