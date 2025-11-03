# Gerekli Flask modüllerini ve OpenAI kütüphanesini içe aktar
from flask import Flask, render_template, request, redirect, url_for, session, send_file
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

# .env dosyasını yükle
load_dotenv()
print("Yüklenen API KEY:", os.getenv("OPENAI_API_KEY"))

# =========================================================
# API AYARLARI
# =========================================================
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "gpt-4o-mini"
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "-DRku0m96CSNkK6Qg8MesumwwbfyRVZzQSBGPtfAFO8")

# Flask uygulamasını başlat
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_key_if_missing")

# OpenAI istemcisini oluştur
client = None
try:
    if not API_KEY:
        raise ValueError("OPENAI_API_KEY ortam değişkeni (.env dosyasında) tanımlı değil.")
    
    client = OpenAI(
        api_key=API_KEY,
        base_url="https://api.openai.com/v1/"
    )
    print("[BİLGİ]: OpenAI istemcisi başarıyla başlatıldı.")
except Exception as e:
    print(f"[HATA]: OpenAI istemcisi başlatılamadı -> {e}")
    client = None


# =========================================================
# YARDIMCI FONKSİYONLAR
# =========================================================

def get_unsplash_image(category, title="", detailed_description=""):
    """Unsplash'dan kategoriye, başlığa ve detaylı açıklamaya göre görsel indir."""
    
    # Kategori bazlı genel arama terimleri
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
    
    # Detaylı açıklamadan ve başlıktan anahtar kelimeler çıkar
    combined_text = (title + " " + detailed_description).lower()
    specific_keywords = []
    
    print(f"[DEBUG]: Arama metni analiz ediliyor: {combined_text[:100]}...")
    
    # Şehir ve ülke isimleri (Seyahat için)
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
            print(f"[BİLGİ]: Lokasyon bulundu: {location}")
            break
    
    # Eğitim kategorisi için özel konular
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
                print(f"[BİLGİ]: Eğitim konusu bulundu: {topic}")
                break
    
    # Spor kategorisi için özel konular
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
                print(f"[BİLGİ]: Spor konusu bulundu: {topic}")
                break
    
    # Yemek kategorisi için özel konular
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
                print(f"[BİLGİ]: Yemek konusu bulundu: {topic}")
                break
    
    # Oyun kategorisi için özel konular
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
                print(f"[BİLGİ]: Oyun konusu bulundu: {topic}")
                break
    
    # Final arama terimi oluştur
    if specific_keywords:
        query = specific_keywords[0] + ",vibrant,high contrast"
        print(f"[BAŞARILI]: Konuya özel arama: {query}")
    else:
        query = category_terms.get(category, "creative,vibrant,colorful") + ",high contrast"
        print(f"[BİLGİ]: Genel kategori araması: {query}")
    
    # Unsplash API yoksa atlayalım
    if not UNSPLASH_ACCESS_KEY or UNSPLASH_ACCESS_KEY == "":
        print("[UYARI]: Unsplash API key yok, gradient arka plan kullanılacak")
        return None
    
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
            print(f"[BAŞARILI]: Unsplash'dan görsel indirildi: {query}")
            return img
        else:
            print(f"[UYARI]: Unsplash API hatası: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"[UYARI]: Unsplash görsel indirilemedi: {e}")
        return None


# =========================================================
# 1️⃣ DETAYLANDIRMA FONKSİYONU
# =========================================================

def generate_detailed_description(category, user_input):
    """Kullanıcının kısa video özetini detaylı açıklamaya dönüştürür."""
    print("\n--- ADIM 1: DETAYLANDIRMA BAŞLADI ---")
    print("CATEGORY:", category)
    print("USER INPUT:", user_input)
    sys.stdout.flush()

    if not client:
        print("[HATA]: API İstemcisi Yok.")
        sys.stdout.flush()
        return None, "API anahtarı ayarlanmamış. Lütfen .env dosyasını kontrol edin."

    prompt = f"""
Bir YouTube içerik üreticisi için '{category}' kategorisinde bir video hazırlanıyor.
Kullanıcının video özeti şu şekilde: '{user_input}'.
Bu özeti alarak SEO uyumlu, ilgi çekici ve YouTube algoritmasının seveceği akıcı bir video açıklamasına dönüştür.
Sadece açıklama metnini döndür.
"""
    print(f"--- ADIM 2: API İsteği Gönderiliyor. Kategori: {category}")
    sys.stdout.flush()
    
    try:
        time.sleep(0.5)
        
        response = client.chat.completions.create(
            model=MODEL_NAME,  # gpt-4o-mini kullanılacak
            messages=[
                {"role": "system", "content": "Sen profesyonel bir YouTube SEO uzmanısın."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        
        # API yanıtını kontrol et
        if response and response.choices and len(response.choices) > 0:
            result = response.choices[0].message.content.strip()
            print("--- ADIM 3: API YANITI BAŞARILI ---")
            print(f"Dönen metin uzunluğu: {len(result)} karakter")
            sys.stdout.flush()
            return result, None
        else:
            print("[HATA]: API yanıtı boş veya geçersiz")
            sys.stdout.flush()
            return None, "API'den geçersiz yanıt alındı."

    except Exception as e:
        print("[HATA - Detaylandırma]: Hata Oluştu!")
        print(f"Hata Tipi: {type(e).__name__}")
        print(f"Hata Mesajı: {str(e)}")
        print(traceback.format_exc())
        sys.stdout.flush()
        
        # Hata mesajını daha anlaşılır hale getir
        error_message = str(e)
        if "authentication" in error_message.lower() or "api_key" in error_message.lower():
            return None, "API anahtarı geçersiz. Lütfen .env dosyanızı kontrol edin."
        elif "quota" in error_message.lower() or "rate_limit" in error_message.lower():
            return None, "API kullanım limitine ulaşıldı. Lütfen daha sonra tekrar deneyin."
        elif "billing" in error_message.lower() or "payment" in error_message.lower():
            return None, "API ödeme sorunu. Lütfen OpenAI hesabınızı kontrol edin."
        else:
            return None, f"API hatası: {error_message[:100]}"


# =========================================================
# 2️⃣ NİHAİ SEO ÜRETİM FONKSİYONU
# =========================================================

def generate_final_seo(category, detailed_description):
    """Detaylı açıklamadan SEO uyumlu başlık, açıklama ve etiket üretir."""
    if not client:
        return None, "API anahtarı ayarlanmamış."

    user_prompt = f"""
Kategori: {category}
Detaylı Açıklama: {detailed_description}

Bu içerik için YouTube SEO optimizasyonu yap. Türkçe karakterleri doğru kullan (ı, ğ, ü, ş, ö, ç, İ).
Yanıtını JSON formatında ver.
"""

    system_prompt = """
Sen dünya standartlarında bir YouTube SEO ve İçerik Uzmanısın. Türkiye'deki YouTube trendlerini çok iyi biliyorsun.

GÖREV: Aşağıdaki içerik için TÜRKÇE, çarpıcı ve SEO uyumlu başlık, açıklama ve etiketler üret.

ÖNEMLİ KURALLAR:
1. BAŞLIKLAR:
   - 3 farklı başlık seçeneği üret
   - Her başlık 50-70 karakter arası olmalı
   - Clickbait ama yalan olmayan başlıklar
   - Emoji kullanabilirsin (🔥, 💯, ⚡, 🎯, ✅ gibi)
   - Türkçe karakterleri MUTLAKA doğru kullan (İ, ı, ğ, ü, ş, ö, ç)

2. AÇIKLAMA:
   - Minimum 250 kelime, maksimum 500 kelime
   - SEO için anahtar kelimeleri 3-4 kez tekrarla
   - Zaman damgaları ekle (örn: 0:00 Giriş, 2:15 Ana Konu)
   - Emoji ve satır boşlukları kullan
   - Call-to-action ekle (beğen, abone ol, yorum yap)
   - Açıklamanın SONUNA 3-5 hashtag ekle (örn: #YKS #Matematik #Eğitim)

3. ETİKETLER:
   - 10-15 adet etiket üret
   - Hem genel hem spesifik etiketler
   - Küçük harfle yaz, boşluk kullanabilirsin
   - # işareti KULLANMA

4. SEO SKORU:
   - Her video için FARKLI bir skor ver (65-95 arası)
   - İçerik kalitesine göre gerçekçi hesapla

ÇIKTI FORMATI:
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
        
        print("\n=== API'DEN GELEN SEO ÇIKTISI ===")
        print(raw_output)
        print("=================================\n")

        try:
            parsed_json = json.loads(raw_output)
            
            # Varsayılan değerler ekle
            if 'title' not in parsed_json or not parsed_json['title']:
                parsed_json['title'] = ["🎯 Başlık Oluşturulamadı"]
            
            if 'tags' not in parsed_json or not parsed_json['tags']:
                parsed_json['tags'] = ["genel", "video"]
            
            if 'description' not in parsed_json or not parsed_json['description']:
                parsed_json['description'] = "Açıklama oluşturulamadı."
            
            if 'seo_score' not in parsed_json:
                # Otomatik skor hesapla
                score = 50
                title_list = parsed_json.get('title', [])
                tags_list = parsed_json.get('tags', [])
                desc_text = parsed_json.get('description', '')
                
                if len(title_list) >= 3: score += 10
                if any(char in str(title_list) for char in ['🔥', '💯', '⚡', '🎯', '✅']): score += 5
                if len(tags_list) >= 10: score += 12
                if len(desc_text.split()) >= 250: score += 15
                if '#' in desc_text: score += 5
                
                parsed_json['seo_score'] = min(score, 95)
                print(f"  → Hesaplanan SEO Skoru: {parsed_json['seo_score']}")
            else:
                print(f"  → API'den Gelen SEO Skoru: {parsed_json.get('seo_score')}")
            
            print(f"[BAŞARILI]: JSON başarıyla parse edildi!")
            
            return parsed_json, None
            
        except json.JSONDecodeError as je:
            print(f"[HATA]: JSON Parse Hatası: {je}")
            return {
                "title": ["❌ JSON Hatası"],
                "description": raw_output,
                "tags": ["hata"],
                "seo_score": 0
            }, None

    except Exception as e:
        print("[HATA - Final SEO]:", traceback.format_exc())
        error_type = str(e).split(': ')[0] if ':' in str(e) else str(e)
        return None, f"API İsteği Başarısız: {error_type}"


# =========================================================
# 3️⃣ THUMBNAIL FONKSİYONLARI
# =========================================================

def generate_thumbnail_design(category, title, seo_score):
    """Yapay zeka ile thumbnail tasarım konsepti üretir."""
    if not client:
        return None, "API anahtarı ayarlanmamış."

    user_prompt = f"""
Video Kategorisi: {category}
Video Başlığı: {title}
SEO Skoru: {seo_score}

Bu video için PROFESYONEL bir YouTube thumbnail tasarım konsepti oluştur.
ÖNEMLI: main_text için MUTLAKA bu başlığı kullan: "{title}"
Yanıtını JSON formatında ver.
"""

    system_prompt = """
Sen dünya çapında ünlü bir YouTube thumbnail tasarımcısısın.

GÖREV: Milyonlarca tıklama alacak bir thumbnail konsepti oluştur.

ÇIKTI FORMATI:
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
    "emoji": "🔥",
    "style": "bold_impact"
}

KURALLAR:
1. main_text: Maksimum 4-5 KELİME, BÜYÜK HARF
2. text_position: "center", "top", "bottom", "left"
3. overlay_opacity: 0.5-0.7 arası (arka plan görünür olmalı)
4. Yüksek kontrast renkler kullan
5. emoji: TEK emoji, başlığa uygun
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
        print("\n=== THUMBNAIL TASARIM ===")
        print(raw_output)
        print("========================\n")

        try:
            design_data = json.loads(raw_output)
            
            # Varsayılan değerler
            if 'text_position' not in design_data:
                design_data['text_position'] = 'center'
            if 'emoji' not in design_data:
                design_data['emoji'] = '🎯'
            if 'effects' not in design_data:
                design_data['effects'] = {
                    'glow': True,
                    'shadow_intensity': 0.8,
                    'text_outline_width': 4
                }
            
            return design_data, None
            
        except json.JSONDecodeError as je:
            print(f"[HATA]: Thumbnail JSON Hatası: {je}")
            return None, "Tasarım önerisi oluşturulamadı."

    except Exception as e:
        print("[HATA - Thumbnail Design]:", traceback.format_exc())
        return None, f"Thumbnail tasarımı başarısız: {str(e)}"


def create_thumbnail_image(design_data, category, title="", detailed_description=""):
    """Profesyonel thumbnail görseli oluşturur."""
    try:
        width, height = 1280, 720
        
        # 1. Arka plan al - Detaylı açıklamayı da gönder
        print(f"[BİLGİ]: {category} kategorisi için arka plan hazırlanıyor...")
        background = get_unsplash_image(category, title, detailed_description)
        
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        if background:
            # Görseli resize ve crop et
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
            
            # Kontrast ve netlik artır
            enhancer = ImageEnhance.Contrast(background)
            background = enhancer.enhance(1.3)
            enhancer = ImageEnhance.Sharpness(background)
            background = enhancer.enhance(1.2)
            
        else:
            # Gradient arka plan
            print("[BİLGİ]: Gradient arka plan oluşturuluyor")
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
        
        # 2. ÇOK GÜÇLÜ Overlay - Parlak arka planda bile font okunur
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        
        colors = design_data.get('colors', {})
        overlay_start = hex_to_rgb(colors.get('overlay_start', '#000000'))
        overlay_end = hex_to_rgb(colors.get('overlay_end', '#000000'))
        overlay_opacity = colors.get('overlay_opacity', 0.75)  # 0.70'ten 0.75'e çıktı
        
        # Çok agresif gradient overlay - metin bölgesi ÇOK koyu
        for y in range(height):
            ratio = y / height
            
            # Merkezi koruma, kenarları maksimum koyulaştırma
            center_ratio = abs(0.5 - ratio) * 3.0  # 2.5'ten 3.0'a çıktı
            adjusted_opacity = overlay_opacity + (center_ratio * 0.22)  # 0.20'den 0.22'ye
            
            r = int(overlay_start[0] + (overlay_end[0] - overlay_start[0]) * ratio)
            g = int(overlay_start[1] + (overlay_end[1] - overlay_start[1]) * ratio)
            b = int(overlay_start[2] + (overlay_end[2] - overlay_start[2]) * ratio)
            alpha = int(255 * min(adjusted_opacity, 0.92))  # 0.90'dan 0.92'ye
            draw_overlay.rectangle([(0, y), (width, y + 1)], fill=(r, g, b, alpha))
        
        background = background.convert('RGBA')
        background = Image.alpha_composite(background, overlay)
        background = background.convert('RGB')
        
        # 3. Metin ekle
        draw = ImageDraw.Draw(background)
        
        main_text = design_data.get('main_text', 'BAŞLIK').upper()
        sub_text = design_data.get('sub_text', '')
        emoji = design_data.get('emoji', '')
        
        # Font yükle - EN KALIN FONTLARI ÖNCELELE
        try:
            # Çok kalın fontları öncelikle dene
            font_paths = [
                "C:\\Windows\\Fonts\\impact.ttf",        # En kalın, YouTube'da çok kullanılır
                "C:\\Windows\\Fonts\\IMPACTED.TTF",      # Impact variant
                "C:\\Windows\\Fonts\\ariblk.ttf",        # Arial Black - çok kalın
                "C:\\Windows\\Fonts\\ARLRDBD.TTF",       # Arial Rounded Bold
                "C:\\Windows\\Fonts\\calibrib.ttf",      # Calibri Bold
                "C:\\Windows\\Fonts\\BAUHS93.TTF",       # Bauhaus 93 - Bold
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux Bold
                "/System/Library/Fonts/Impact.ttf",      # macOS Impact
            ]
            
            main_font = None
            font_name = "default"
            
            for font_path in font_paths:
                try:
                    initial_size = 110  # Biraz daha büyük başla
                    test_font = ImageFont.truetype(font_path, initial_size)
                    
                    test_text = emoji + " " + main_text if emoji else main_text
                    bbox = draw.textbbox((0, 0), test_text, font=test_font)
                    text_width = bbox[2] - bbox[0]
                    
                    max_width = width - 120  # Daha fazla padding
                    if text_width > max_width:
                        scale = max_width / text_width
                        new_size = int(initial_size * scale * 0.85)  # Biraz daha küçült (güvenli alan)
                        main_font = ImageFont.truetype(font_path, new_size)
                    else:
                        main_font = test_font
                    
                    font_name = font_path.split("\\")[-1].split("/")[-1]
                    print(f"[BAŞARILI]: Font yüklendi: {font_name}")
                    break
                except:
                    continue
            
            if not main_font:
                print("[UYARI]: Sistem fontu bulunamadı, varsayılan font kullanılıyor")
                main_font = ImageFont.load_default()
                font_name = "default"
            
            # Alt metin için de kalın font
            if font_name != "default":
                try:
                    sub_font = ImageFont.truetype(font_paths[0], 55)  # Biraz daha büyük alt metin
                except:
                    sub_font = ImageFont.load_default()
            else:
                sub_font = ImageFont.load_default()
            
        except Exception as e:
            print(f"[UYARI]: Font yüklenemedi: {e}")
            main_font = ImageFont.load_default()
            sub_font = ImageFont.load_default()
        
        text_color = hex_to_rgb(colors.get('text_main', '#FFFFFF'))
        stroke_color = hex_to_rgb(colors.get('text_stroke', '#000000'))
        
        effects = design_data.get('effects', {})
        stroke_width = effects.get('text_outline_width', 7)  # 6'dan 7'ye çıktı (daha kalın kontur)
        
        # Emoji kontrolü - Eğer emoji yüklenemiyorsa boş bırak
        emoji = design_data.get('emoji', '')
        
        # Emoji karakterini temizle - sadece gerçek emoji bırak
        if emoji and len(emoji) > 0:
            # Unicode emoji aralığını kontrol et
            emoji_char = emoji[0] if len(emoji) > 0 else ''
            emoji_code = ord(emoji_char) if emoji_char else 0
            
            # Gerçek emoji mi yoksa box character mı kontrol et
            # Box character (□) unicode: 9633 (0x25A1)
            # Gerçek emojiler genelde 0x1F300+ aralığında
            if emoji_code < 0x1F300 or emoji_code == 9633:
                print(f"[UYARI]: Geçersiz emoji karakteri tespit edildi (code: {emoji_code}), emoji kullanılmayacak")
                emoji = ''
            else:
                print(f"[BİLGİ]: Geçerli emoji kullanılıyor: {emoji}")
        
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
        
        # Stroke efekti
        for offset_x in range(-stroke_width, stroke_width + 1):
            for offset_y in range(-stroke_width, stroke_width + 1):
                if offset_x*offset_x + offset_y*offset_y <= stroke_width*stroke_width:
                    draw.text((x + offset_x, y + offset_y), full_text, 
                             font=main_font, fill=stroke_color)
        
        draw.text((x, y), full_text, font=main_font, fill=text_color)
        
        # Alt metin
        if sub_text:
            bbox_sub = draw.textbbox((0, 0), sub_text, font=sub_font)
            sub_width = bbox_sub[2] - bbox_sub[0]
            x_sub = (width - sub_width) // 2
            y_sub = y + text_height + 30
            
            for offset_x in range(-3, 4):
                for offset_y in range(-3, 4):
                    if offset_x*offset_x + offset_y*offset_y <= 9:
                        draw.text((x_sub + offset_x, y_sub + offset_y), sub_text, 
                                 font=sub_font, fill=stroke_color)
            
            draw.text((x_sub, y_sub), sub_text, font=sub_font, fill=text_color)
        
        # 4. Final: Keskinlik
        background = background.filter(ImageFilter.SHARPEN)
        
        img_io = io.BytesIO()
        background.save(img_io, 'JPEG', quality=95)
        img_io.seek(0)
        
        img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
        
        return img_io, img_base64, None
        
    except Exception as e:
        print("[HATA - Thumbnail Creation]:", traceback.format_exc())
        return None, None, f"Görsel oluşturulamadı: {str(e)}"


# =========================================================
# FLASK ROUTES
# =========================================================

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        category = request.form.get('category')
        
        if not category:
            return render_template('index.html', error_message="Lütfen bir video kategorisi seçin.")
        
        session['category'] = category
        return redirect(url_for('detay'))
        
    return render_template('index.html')


@app.route('/detay', methods=['GET', 'POST'])
def detay():
    print("\n=== DETAY ROUTE BAŞLADI ===")
    print("SESSION VERİLERİ:", dict(session))
    print("REQUEST METHOD:", request.method)
    sys.stdout.flush()
    
    category = session.get('category')
    error_message_from_url = request.args.get('error_message')
    
    # URL'den gelen hata mesajını göster ama bir kez gösterince temizle
    if error_message_from_url:
        print(f"[UYARI]: URL'den hata mesajı alındı: {error_message_from_url}")
        sys.stdout.flush()

    if not category:
        print("[HATA]: Kategori session'da yok, index'e yönlendiriliyor")
        sys.stdout.flush()
        return redirect(url_for('index'))

    if request.method == 'POST':
        user_input = request.form.get('user_input')
        
        if not user_input:
            return render_template('detay.html', category=category, error_message="Lütfen video içeriği hakkında kısa bir özet girin.")

        print(f"\n[BİLGİ]: Detaylandırma başlatılıyor...")
        print(f"Kullanıcı girişi: {user_input[:50]}...")
        sys.stdout.flush()
        
        detailed_description, error = generate_detailed_description(category, user_input)

        print(f"[DEBUG]: API Sonucu:")
        print(f"  - detailed_description mevcut: {detailed_description is not None}")
        print(f"  - error mevcut: {error is not None}")
        if detailed_description:
            print(f"  - Açıklama uzunluğu: {len(detailed_description)} karakter")
        if error:
            print(f"  - Hata mesajı: {error}")
        sys.stdout.flush()

        if error:
            print(f"[HATA]: API'den hata döndü, kullanıcıya gösteriliyor")
            sys.stdout.flush()
            return render_template('detay.html', category=category, user_input=user_input, error_message=error)
        
        if not detailed_description:
            print(f"[HATA]: Detaylı açıklama boş ama error de yok!")
            sys.stdout.flush()
            return render_template('detay.html', category=category, user_input=user_input, error_message="Detaylı açıklama oluşturulamadı. Lütfen tekrar deneyin.")
        
        print(f"[BAŞARILI]: Detaylı açıklama oluşturuldu ({len(detailed_description)} karakter)")
        print(f"[BİLGİ]: Session'a kaydediliyor ve optimize'a yönlendiriliyor...")
        sys.stdout.flush()
        
        session['detailed_description'] = detailed_description
        session.modified = True  # Session'ın güncellendiğini belirt
        
        print(f"[DEBUG]: Session kaydedildi. İçerik: {list(session.keys())}")
        sys.stdout.flush()
        
        return redirect(url_for('optimize'))

    # GET isteği - sadece URL'den gelen hata mesajını göster
    return render_template('detay.html', category=category, error_message=error_message_from_url)


@app.route('/optimize', methods=['GET', 'POST'])
def optimize():
    print("SESSION VERİLERİ:", dict(session))
    
    category = session.get('category')
    detailed_description = session.get('detailed_description')

    if not category or not detailed_description:
        return redirect(url_for('detay', error_message="Oturum verisi eksik. Lütfen kategoriyi ve özeti tekrar girin."))

    seo_data, error = generate_final_seo(category, detailed_description)

    if error:
        return redirect(url_for('detay', error_message=error))

    # Veriyi işle
    title_data = seo_data.get('title', ['Başlık bulunamadı'])
    
    if isinstance(title_data, list) and len(title_data) > 0:
        title_list = title_data
        title_first = title_data[0]
    else:
        title_list = [str(title_data)]
        title_first = str(title_data)

    tags_data = seo_data.get('tags', ['etiket_yok'])
    
    if isinstance(tags_data, list) and len(tags_data) > 0:
        tags_list = tags_data
        tags_joined = ', '.join(tags_data)
    else:
        tags_list = [str(tags_data)]
        tags_joined = str(tags_data)

    description = seo_data.get('description', 'Açıklama bulunamadı.')
    seo_score = seo_data.get('seo_score', 'N/A')
    
    # Session'a kaydet
    session['title_first'] = title_first
    session['seo_score'] = seo_score
    
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
def generate_thumbnail():
    """Thumbnail oluşturma endpoint'i"""
    try:
        category = session.get('category')
        title_first = session.get('title_first')
        seo_score = session.get('seo_score', 80)
        
        if not title_first:
            return {"error": "Başlık bulunamadı"}, 400
        
        design_data, error = generate_thumbnail_design(category, title_first, seo_score)
        
        if error:
            return {"error": error}, 500
        
        img_io, img_base64, error = create_thumbnail_image(design_data, category, title_first, session.get('detailed_description', ''))
        
        if error:
            return {"error": error}, 500
        
        # Session'a kaydet
        session['thumbnail_design'] = design_data
        
        return {
            "success": True,
            "image_base64": img_base64,
            "design_data": design_data
        }
        
    except Exception as e:
        print("[HATA - Generate Thumbnail]:", traceback.format_exc())
        return {"error": str(e)}, 500


@app.route('/download-thumbnail')
def download_thumbnail():
    """Thumbnail indirme endpoint'i"""
    try:
        design_data = session.get('thumbnail_design')
        category = session.get('category', 'Diğer')
        title_first = session.get('title_first', '')
        detailed_description = session.get('detailed_description', '')
        
        if not design_data:
            return "Thumbnail bulunamadı", 404
        
        img_io, _, error = create_thumbnail_image(design_data, category, title_first, detailed_description)
        
        if error:
            return f"Hata: {error}", 500
        
        img_io.seek(0)
        return send_file(
            img_io,
            mimetype='image/jpeg',
            as_attachment=True,
            download_name='youtube_thumbnail.jpg'
        )
        
    except Exception as e:
        print("[HATA - Download Thumbnail]:", traceback.format_exc())
        return f"Hata: {str(e)}", 500


# =========================================================
# MAIN
# =========================================================
if __name__ == '__main__':
    app.run(debug=True)