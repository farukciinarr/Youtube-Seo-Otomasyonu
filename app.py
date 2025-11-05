# Gerekli Flask modüllerini ve OpenAI kütüphanesini içe aktar
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from openai import OpenAI
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import json
import os
import traceback
import base64
import io
import random
import requests
import time
import sys
import re
import logging
from logging.handlers import RotatingFileHandler

# .env dosyasını yükle
load_dotenv()

# =========================================================
# GÜVENLIK AYARLARI - LOGGING
# =========================================================
if not os.path.exists('logs'):
    os.mkdir('logs')

file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240000, backupCount=10, encoding='utf-8')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)

# =========================================================
# API AYARLARI - GÜVENLİ (HARDCODED KEY YOK!)
# =========================================================
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "gpt-4o-mini"
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

# =========================================================
# FLASK UYGULAMASI BAŞLATMA VE YAPILANDIRMA
# =========================================================

# Flask uygulamasını başlat
app = Flask(__name__)

# ✓ Secret key kontrolü (SADECE 1 KEZ Tanimlanmali)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    print("[FATAL]: FLASK_SECRET_KEY tanımlı değil!")
    sys.exit(1)

# ✓ CSRF koruması (SADECE 1 KEZ Tanimlanmali)
csrf = CSRFProtect(app)

# ✓ Session güvenlik ayarları
debug_mode = os.getenv("FLASK_DEBUG", "False").lower() == "true"
app.config.update(
    SESSION_COOKIE_SECURE=not debug_mode,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=1800,
    MAX_CONTENT_LENGTH=5 * 1024 * 1024
)

# ✓ Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('YouTube Otomasyonu başlatıldı')

# =========================================================
# OPENAI CLIENT - GÜVENLİK KONTROLÜ
# =========================================================
client = None
try:
    if not API_KEY:
        raise ValueError("OPENAI_API_KEY tanımlı değil")
    
    client = OpenAI(api_key=API_KEY, base_url="https://api.openai.com/v1/")
    test_response = client.models.list()
    app.logger.info("[✓] OpenAI API geçerli")
    print("[BİLGİ]: OpenAI istemcisi başarıyla başlatıldı.")
except Exception as e:
    app.logger.error(f"[✗] OpenAI hatası: {e}")
    print(f"[FATAL]: OpenAI API geçersiz! {e}")
    sys.exit(1)

# =========================================================
# GÜVENLİK FONKSİYONLARI
# =========================================================
def sanitize_input(text, max_length=1000):
    if not text or not isinstance(text, str):
        return ""
    text = text.strip()
    text = re.sub(r'[<>]', '', text)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    if len(text) > max_length:
        text = text[:max_length]
    return text

def validate_category(category):
    valid = ["Vlog", "Yemek", "Podcast", "Travel", "Spor", "Oyun", "Eğitim", "Teknoloji", "Diğer"]
    return category in valid

# =========================================================
# ERROR HANDLERS
# =========================================================
@app.errorhandler(404)
def not_found_error(error):
    app.logger.warning(f'404: {request.url}')
    return render_template('index.html', error_message="Sayfa bulunamadı"), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'500: {error}', exc_info=True)
    if app.debug:
        return str(error), 500
    return render_template('index.html', error_message="Bir sorun oluştu"), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    app.logger.warning(f'Rate limit: {request.remote_addr}')
    return render_template('index.html', error_message="Çok fazla istek"), 429

# =========================================================
# YARDIMCI FONKSİYONLAR
# =========================================================
def get_unsplash_image(category, title="", detailed_description=""):
    if not UNSPLASH_ACCESS_KEY:
        app.logger.info("Unsplash key yok, gradient kullanılacak")
        return None
    
    category_terms = {
        "Vlog": "lifestyle,people,daily life,vibrant",
        "Yemek": "food,cooking,delicious meal,colorful",
        "Podcast": "microphone,podcast studio,recording,professional",
        "Travel": "travel,adventure,beautiful landscape,scenic",
        "Spor": "fitness,gym,sports training,dynamic",
        "Oyun": "gaming,esports,neon lights,colorful",
        "Eğitim": "education,learning,study,bright",
        "Teknoloji": "technology,computer,modern tech,colorful",
        "Diğer": "creative,abstract,vibrant,colorful"
    }
    
    combined_text = (title + " " + detailed_description).lower()
    specific_keywords = []
    
    locations = {
        "panama": "panama city,panama landscape,central america",
        "istanbul": "istanbul,turkey,bosphorus",
        "paris": "paris,eiffel tower,france",
        "tokyo": "tokyo,japan,cityscape",
        "new york": "new york,manhattan,usa",
        "londra": "london,big ben,england",
        "dubai": "dubai,burj khalifa,uae",
        "bali": "bali,indonesia,tropical",
        "roma": "rome,colosseum,italy",
        "barselona": "barcelona,sagrada familia,spain",
        "amsterdam": "amsterdam,netherlands,canals",
        "prag": "prague,czech republic,castle"
    }
    
    for location, keywords in locations.items():
        if location in combined_text:
            specific_keywords.append(keywords)
            app.logger.info(f"Lokasyon: {location}")
            break
    
    if not specific_keywords and category == "Eğitim":
        education_topics = {
            "matematik": "mathematics,colorful equations,numbers,geometry",
            "integral": "calculus,mathematics,colorful formulas",
            "fizik": "physics,science,colorful laboratory",
            "kimya": "chemistry,colorful laboratory,molecules",
            "biyoloji": "biology,nature,colorful microscope",
            "tarih": "history,ancient,colorful books",
            "coğrafya": "geography,colorful maps,globe",
            "edebiyat": "literature,colorful books,reading",
            "yks": "study,exam preparation,colorful books",
            "geometri": "geometry,colorful shapes,mathematics"
        }
        for topic, keywords in education_topics.items():
            if topic in combined_text:
                specific_keywords.append(keywords)
                app.logger.info(f"Eğitim: {topic}")
                break
    
    if not specific_keywords and category == "Spor":
        sport_topics = {
            "futbol": "football,soccer,colorful stadium,action",
            "basketbol": "basketball,colorful court,action",
            "voleybol": "volleyball,colorful net,action",
            "fitness": "gym,workout,colorful dumbbells,dynamic",
            "koşu": "running,marathon,colorful track,action",
            "yüzme": "swimming,colorful pool,water,action",
            "yoga": "yoga,meditation,colorful mat,peaceful",
            "bacak": "leg workout,gym,colorful fitness,muscles",
            "kol": "arm workout,colorful dumbbells,biceps,gym"
        }
        for topic, keywords in sport_topics.items():
            if topic in combined_text:
                specific_keywords.append(keywords)
                app.logger.info(f"Spor: {topic}")
                break
    
    if not specific_keywords and category == "Yemek":
        food_topics = {
            "pasta": "pasta,colorful italian food,delicious",
            "pizza": "pizza,colorful cheese,restaurant",
            "tatlı": "dessert,colorful sweet,cake",
            "pilav": "rice,colorful turkish food,plate",
            "çorba": "soup,hot meal,colorful bowl",
            "salata": "salad,healthy,colorful vegetables",
            "et": "meat,steak,colorful grill",
            "balık": "fish,seafood,colorful ocean",
            "hamburger": "burger,colorful fast food,delicious",
            "makarna": "pasta,colorful noodles,italian"
        }
        for topic, keywords in food_topics.items():
            if topic in combined_text:
                specific_keywords.append(keywords)
                app.logger.info(f"Yemek: {topic}")
                break
    
    if not specific_keywords and category == "Oyun":
        game_topics = {
            "lol": "league of legends,gaming,colorful esports",
            "valorant": "valorant,fps,colorful gaming",
            "minecraft": "minecraft,blocks,colorful gaming",
            "fortnite": "fortnite,battle royale,colorful gaming",
            "cs": "counter strike,fps,colorful gaming",
            "fifa": "fifa,football game,colorful soccer",
            "gta": "gta,open world,colorful gaming"
        }
        for topic, keywords in game_topics.items():
            if topic in combined_text:
                specific_keywords.append(keywords)
                app.logger.info(f"Oyun: {topic}")
                break
    
    if specific_keywords:
        query = specific_keywords[0] + ",vibrant,high contrast"
    else:
        query = category_terms.get(category, "creative,vibrant,colorful") + ",high contrast"
    
    try:
        url = "https://api.unsplash.com/photos/random"
        params = {
            "query": query,
            "orientation": "landscape",
            "client_id": UNSPLASH_ACCESS_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            image_url = data['urls']['regular']
            img_response = requests.get(image_url, timeout=10)
            img = Image.open(io.BytesIO(img_response.content))
            app.logger.info(f"Unsplash başarılı: {query}")
            return img
        else:
            app.logger.warning(f"Unsplash hata: {response.status_code}")
            return None
    except Exception as e:
        app.logger.warning(f"Unsplash hata: {e}")
        return None

# =========================================================
# DETAYLANDIRMA
# =========================================================
def generate_detailed_description(category, user_input):
    app.logger.info(f"Detaylandırma: {category}, {len(user_input)} karakter")
    if not client:
        return None, "API yok"

    prompt = f"""
Bir YouTube içerik üreticisi için '{category}' kategorisinde bir video hazırlanıyor.
Kullanıcının video özeti: '{user_input}'.
Bu özeti SEO uyumlu, ilgi çekici açıklamaya dönüştür.
Sadece açıklama metnini döndür.
"""
    try:
        time.sleep(0.5)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Sen profesyonel YouTube SEO uzmanısın."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        if response and response.choices:
            result = response.choices[0].message.content.strip()
            app.logger.info(f"Detaylandırma OK: {len(result)} karakter")
            return result, None
        return None, "API yanıt yok"
    except Exception as e:
        app.logger.error(f"Detaylandırma hata: {e}")
        error_message = str(e)
        if "authentication" in error_message.lower():
            return None, "API anahtarı geçersiz"
        elif "quota" in error_message.lower():
            return None, "API limit aşıldı"
        return None, f"API hatası: {error_message[:100]}"

# =========================================================
# SEO ÜRETİMİ
# =========================================================
def generate_final_seo(category, detailed_description):
    if not client:
        return None, "API yok"

    user_prompt = f"""
Kategori: {category}
Detaylı Açıklama: {detailed_description}

Bu içerik için YouTube SEO optimizasyonu yap. Türkçe karakterleri doğru kullan.
Yanıtını JSON formatında ver.
"""

    system_prompt = """
Sen YouTube SEO uzmanısın.

GÖREV: Türkçe, çarpıcı ve SEO uyumlu başlık, açıklama ve etiketler üret.

KURALLAR:
1. BAŞLIKLAR: 3 seçenek, 50-70 karakter, emoji kullan
2. AÇIKLAMA: 250-500 kelime, SEO keywords, hashtag'ler
3. ETİKETLER: 10-15 adet, # işareti yok
4. SEO SKORU: 65-95 arası

ÇIKTI:
{
    "title": ["Başlık 1", "Başlık 2", "Başlık 3"],
    "description": "Açıklama...",
    "tags": ["etiket1", "etiket2"],
    "seo_score": 85
}
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.9,
            max_tokens=2000
        )
        raw_output = response.choices[0].message.content.strip()
        app.logger.info("SEO çıktısı alındı")
        
        try:
            parsed_json = json.loads(raw_output)
            if 'title' not in parsed_json or not parsed_json['title']:
                parsed_json['title'] = ["🎯 Başlık Yok"]
            if 'tags' not in parsed_json or not parsed_json['tags']:
                parsed_json['tags'] = ["genel", "video"]
            if 'description' not in parsed_json or not parsed_json['description']:
                parsed_json['description'] = "Açıklama yok"
            if 'seo_score' not in parsed_json:
                score = 50
                if len(parsed_json.get('title', [])) >= 3: score += 10
                if len(parsed_json.get('tags', [])) >= 10: score += 12
                if len(parsed_json.get('description', '').split()) >= 250: score += 15
                parsed_json['seo_score'] = min(score, 95)
            
            app.logger.info(f"SEO OK: Skor {parsed_json['seo_score']}")
            return parsed_json, None
        except json.JSONDecodeError:
            app.logger.error("JSON parse hatası")
            return {
                "title": ["❌ JSON Hatası"],
                "description": raw_output,
                "tags": ["hata"],
                "seo_score": 0
            }, None
    except Exception as e:
        app.logger.error(f"SEO hata: {e}")
        return None, f"API başarısız: {str(e)[:50]}"

# =========================================================
# THUMBNAIL TASARIM
# =========================================================
def generate_thumbnail_design(category, title, seo_score):
    if not client:
        return None, "API yok"

    user_prompt = f"""
Video Kategorisi: {category}
Video Başlığı: {title}
SEO Skoru: {seo_score}

Profesyonel YouTube thumbnail konsepti oluştur.
ÖNEMLI: main_text için bu başlığı kullan: "{title}"
JSON formatında ver.
"""

system_prompt = """  # type: ignore
Sen thumbnail tasarımcısısın.

ÇIKTI:
{
    "main_text": "ANA BAŞLIK",
    "sub_text": "alt başlık",
    "text_position": "center",
    "colors": {
        "overlay_start": "#000000",
        "overlay_end": "#1a1a1a",
        "overlay_opacity": 0.6,
        "text_main": "#FFFFFF",
        "text_stroke": "#000000",
        "accent": "#FFD93D",
        "shadow": "#FF0000"
    },
    "effects": {
        "glow": true,
        "shadow_intensity": 0.8,
        "text_outline_width": 4
    },
    "style": "bold_impact"
}

KURALLAR:
1. main_text: Max 5 kelime, BÜYÜK HARF
2. text_position: center/top/bottom/left
3. overlay_opacity: 0.5-0.7
4. Yüksek kontrast
5. ASLA emoji kullanma, sadece metin
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.85,
            max_tokens=700
        )
        raw_output = response.choices[0].message.content.strip()
        app.logger.info("Thumbnail tasarım alındı")
        
        try:
            design_data = json.loads(raw_output)
            if 'text_position' not in design_data:
                design_data['text_position'] = 'center'
            if 'emoji' not in design_data:
                design_data['emoji'] = '🎯'
            if 'effects' not in design_data:
                design_data['effects'] = {'glow': True, 'shadow_intensity': 0.8, 'text_outline_width': 4}
            return design_data, None
        except json.JSONDecodeError:
            app.logger.error("Thumbnail JSON hatası")
            return None, "Tasarım oluşturulamadı"
    except Exception as e:
        app.logger.error(f"Thumbnail tasarım hata: {e}")
        return None, str(e)[:50]

# =========================================================
# THUMBNAIL GÖRSEL OLUŞTURMA
# =========================================================
def create_thumbnail_image(design_data, category, title="", detailed_description=""):
    try:
        width, height = 1280, 720
        app.logger.info(f"Thumbnail oluşturuluyor: {category}")
        background = get_unsplash_image(category, title, detailed_description)
        
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        if background:
            bg_width, bg_height = background.size
            aspect = bg_width / bg_height
            target_aspect = width / height
            if aspect > target_aspect:
                new_height = height
                new_width = int(height * aspect)
            else:
                new_width = width
                new_height = int(width / aspect)
            background = background.resize((new_width, new_height), Image.Resampling.LANCZOS)
            left = (new_width - width) // 2
            top = (new_height - height) // 2
            background = background.crop((left, top, left + width, top + height))
            enhancer = ImageEnhance.Contrast(background)
            background = enhancer.enhance(1.3)
            enhancer = ImageEnhance.Sharpness(background)
            background = enhancer.enhance(1.2)
        else:
            background = Image.new('RGB', (width, height))
            draw_bg = ImageDraw.Draw(background)
            gradient_colors = [
                ('#FF6B6B', '#4ECDC4'),
                ('#667eea', '#764ba2'),
                ('#f093fb', '#f5576c'),
                ('#4facfe', '#00f2fe'),
                ('#43e97b', '#38f9d7'),
            ]
            start_color, end_color = random.choice(gradient_colors)
            start_rgb = hex_to_rgb(start_color)
            end_rgb = hex_to_rgb(end_color)
            for y in range(height):
                ratio = y / height
                r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio)
                g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio)
                b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio)
                draw_bg.rectangle([(0, y), (width, y + 1)], fill=(r, g, b))
        
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        colors = design_data.get('colors', {})
        overlay_start = hex_to_rgb(colors.get('overlay_start', '#000000'))
        overlay_end = hex_to_rgb(colors.get('overlay_end', '#000000'))
        overlay_opacity = colors.get('overlay_opacity', 0.75)
        
        for y in range(height):
            ratio = y / height
            center_ratio = abs(0.5 - ratio) * 3.0
            adjusted_opacity = overlay_opacity + (center_ratio * 0.22)
            r = int(overlay_start[0] + (overlay_end[0] - overlay_start[0]) * ratio)
            g = int(overlay_start[1] + (overlay_end[1] - overlay_start[1]) * ratio)
            b = int(overlay_start[2] + (overlay_end[2] - overlay_start[2]) * ratio)
            alpha = int(255 * min(adjusted_opacity, 0.92))
            draw_overlay.rectangle([(0, y), (width, y + 1)], fill=(r, g, b, alpha))
        
        background = background.convert('RGBA')
        background = Image.alpha_composite(background, overlay)
        background = background.convert('RGB')
        
        draw = ImageDraw.Draw(background)
        main_text = design_data.get('main_text', 'BAŞLIK').upper()
        sub_text = design_data.get('sub_text', '')
        emoji = ''  # ← Emoji'yi tamamen devre dışı bırak
        
        try:
            font_paths = [
                "C:\\Windows\\Fonts\\impact.ttf",
                "C:\\Windows\\Fonts\\IMPACTED.TTF",
                "C:\\Windows\\Fonts\\ariblk.ttf",
                "C:\\Windows\\Fonts\\ARLRDBD.TTF",
                "C:\\Windows\\Fonts\\calibrib.ttf",
                "C:\\Windows\\Fonts\\BAUHS93.TTF",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Impact.ttf",
            ]
            main_font = None
            for font_path in font_paths:
                try:
                    initial_size = 110
                    test_font = ImageFont.truetype(font_path, initial_size)
                    test_text = emoji + " " + main_text if emoji else main_text
                    bbox = draw.textbbox((0, 0), test_text, font=test_font)
                    text_width = bbox[2] - bbox[0]
                    max_width = width - 120
                    if text_width > max_width:
                        scale = max_width / text_width
                        new_size = int(initial_size * scale * 0.85)
                        main_font = ImageFont.truetype(font_path, new_size)
                    else:
                        main_font = test_font
                    app.logger.info(f"Font yüklendi: {font_path.split('/')[-1]}")
                    break
                except:
                    continue
            if not main_font:
                main_font = ImageFont.load_default()
            try:
                sub_font = ImageFont.truetype(font_paths[0], 55)
            except:
                sub_font = ImageFont.load_default()
        except:
            main_font = ImageFont.load_default()
            sub_font = ImageFont.load_default()
        
        text_color = hex_to_rgb(colors.get('text_main', '#FFFFFF'))
        stroke_color = hex_to_rgb(colors.get('text_stroke', '#000000'))
        effects = design_data.get('effects', {})
        stroke_width = effects.get('text_outline_width', 7)
        
        emoji = ''
        
        full_text = f"{emoji} {main_text}" if emoji else main_text
        bbox = draw.textbbox((0, 0), full_text, font=main_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        text_position = design_data.get('text_position', 'center')
        if text_position == 'center':
            x = (width - text_width) // 2
            y = (height - text_height) // 2
        elif text_position == 'top':
            x = (width - text_width) // 2
            y = 80
        elif text_position == 'bottom':
            x = (width - text_width) // 2
            y = height - text_height - 100
        else:
            x = 80
            y = (height - text_height) // 2
        
        for offset_x in range(-stroke_width, stroke_width + 1):
            for offset_y in range(-stroke_width, stroke_width + 1):
                if offset_x*offset_x + offset_y*offset_y <= stroke_width*stroke_width:
                    draw.text((x + offset_x, y + offset_y), full_text, font=main_font, fill=stroke_color)
        draw.text((x, y), full_text, font=main_font, fill=text_color)
        
        if sub_text:
            bbox_sub = draw.textbbox((0, 0), sub_text, font=sub_font)
            sub_width = bbox_sub[2] - bbox_sub[0]
            x_sub = (width - sub_width) // 2
            y_sub = y + text_height + 30
            for offset_x in range(-3, 4):
                for offset_y in range(-3, 4):
                    if offset_x*offset_x + offset_y*offset_y <= 9:
                        draw.text((x_sub + offset_x, y_sub + offset_y), sub_text, font=sub_font, fill=stroke_color)
            draw.text((x_sub, y_sub), sub_text, font=sub_font, fill=text_color)
        
        background = background.filter(ImageFilter.SHARPEN)
        img_io = io.BytesIO()
        background.save(img_io, 'JPEG', quality=95)
        img_io.seek(0)
        img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
        app.logger.info("Thumbnail oluşturuldu")
        return img_io, img_base64, None
    except Exception as e:
        app.logger.error(f"Thumbnail hata: {e}")
        return None, None, str(e)[:100]

# =========================================================
# FLASK ROUTES
# =========================================================
@app.route('/', methods=['GET', 'POST'])
# @limiter.limit("30 per minute") # <- Bu yorumu fark ettim, test için kapatılmış
def index():
    if request.method == 'POST':
        category = request.form.get('category', '').strip()
        if not category:
            return render_template('index.html', error_message="Kategori seçin")
        if not validate_category(category):
            return render_template('index.html', error_message="Geçersiz kategori")
        session['category'] = category
        app.logger.info(f"Kategori: {category}")
        return redirect(url_for('detay'))
    return render_template('index.html')

@app.route('/detay', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def detay():
    category = session.get('category')
    error_message_from_url = request.args.get('error_message')
    if not category:
        return redirect(url_for('index'))

    if request.method == 'POST':
        user_input = request.form.get('user_input', '')
        user_input = sanitize_input(user_input, max_length=1000)
        if not user_input or len(user_input) < 10:
            return render_template('detay.html', category=category, error_message="En az 10 karakter girin")

        app.logger.info(f"Detaylandırma başlatılıyor: {len(user_input)} karakter")
        detailed_description, error = generate_detailed_description(category, user_input)

        if error:
            app.logger.error(f"Detaylandırma hatası: {error}")
            return render_template('detay.html', category=category, user_input=user_input, error_message=error)
        
        if not detailed_description:
            return render_template('detay.html', category=category, error_message="Detaylı açıklama oluşturulamadı")
        
        session['detailed_description'] = detailed_description
        session.modified = True
        app.logger.info("Detaylandırma başarılı")
        return redirect(url_for('optimize'))

    return render_template('detay.html', category=category, error_message=error_message_from_url)

@app.route('/optimize', methods=['GET', 'POST'])
@limiter.limit("15 per minute")
def optimize():
    category = session.get('category')
    detailed_description = session.get('detailed_description')

    if not category or not detailed_description:
        app.logger.warning("Session verisi eksik")
        return redirect(url_for('detay', error_message="Oturum verisi eksik"))

    seo_data, error = generate_final_seo(category, detailed_description)

    if error:
        app.logger.error(f"SEO hatası: {error}")
        return redirect(url_for('detay', error_message=error))

    title_data = seo_data.get('title', ['Başlık yok'])
    title_list = title_data if isinstance(title_data, list) else [str(title_data)]
    title_first = title_list[0]
    
    tags_data = seo_data.get('tags', ['etiket yok'])
    tags_list = tags_data if isinstance(tags_data, list) else [str(tags_data)]
    tags_joined = ', '.join(tags_list)
    
    description = seo_data.get('description', 'Açıklama yok')
    seo_score = seo_data.get('seo_score', 'N/A')
    
    session['title_first'] = title_first
    session['seo_score'] = seo_score
    
    app.logger.info(f"SEO başarılı - Skor: {seo_score}")
    
    return render_template(
        'results.html',
        category=category,
        title_list=title_list,
        title_first=title_first,
        description=description,
        tags_list=tags_list,
        tags_joined=tags_joined,
        seo_score=seo_score
    )

@app.route('/generate-thumbnail', methods=['POST'])
@limiter.limit("10 per minute")
@csrf.exempt
def generate_thumbnail():
    try:
        category = session.get('category')
        title_first = session.get('title_first')
        seo_score = session.get('seo_score', 80)
        
        data = request.get_json() or {}
        custom_title = data.get('custom_title', '')
        if custom_title:
            custom_title = sanitize_input(custom_title, max_length=50)
            title_first = custom_title if custom_title else title_first
        
        if not title_first:
            app.logger.warning("Thumbnail: Başlık yok")
            return {"error": "Başlık bulunamadı"}, 400
        
        design_data, error = generate_thumbnail_design(category, title_first, seo_score)
        
        if error:
            app.logger.error(f"Thumbnail tasarım hatası: {error}")
            return {"error": error}, 500
        
        img_io, img_base64, error = create_thumbnail_image(
            design_data, category, title_first, session.get('detailed_description', '')
        )
        
        if error:
            app.logger.error(f"Thumbnail oluşturma hatası: {error}")
            return {"error": error}, 500
        
        session['thumbnail_design'] = design_data
        app.logger.info("Thumbnail başarılı")
        
        return {
            "success": True,
            "image_base64": img_base64,
            "design_data": design_data
        }
        
    except Exception as e:
        app.logger.error(f"Thumbnail genel hatası: {e}", exc_info=True)
        return {"error": "Thumbnail oluşturulamadı"}, 500

@app.route('/download-thumbnail')
@limiter.limit("20 per minute")
def download_thumbnail():
    try:
        design_data = session.get('thumbnail_design')
        category = session.get('category', 'Diğer')
        title_first = session.get('title_first', '')
        detailed_description = session.get('detailed_description', '')
        
        if not design_data:
            app.logger.warning("İndirilecek thumbnail yok")
            return "Thumbnail bulunamadı", 404
        
        img_io, _, error = create_thumbnail_image(
            design_data, category, title_first, detailed_description
        )
        
        if error:
            app.logger.error(f"Thumbnail indirme hatası: {error}")
            return f"Hata: {error}", 500
        
        img_io.seek(0)
        app.logger.info("Thumbnail indirildi")
        
        return send_file(
            img_io,
            mimetype='image/jpeg',
            as_attachment=True,
            download_name='youtube_thumbnail.jpg'
        )
        
    except Exception as e:
        app.logger.error(f"İndirme hatası: {e}", exc_info=True)
        return "Thumbnail indirilemedi", 500

# =========================================================
# MAIN
# =========================================================
if __name__ == '__main__':
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    
    if debug_mode:
        app.logger.warning("⚠️ DEBUG MODE AÇIK - Production'da kapatın!")
    
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", 5000))
    
    app.run(debug=debug_mode, host=host, port=port)