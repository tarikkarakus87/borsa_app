# 💼 BIST Portföy Yönetim Sistemi (PMS) Kurulum Rehberi

Bu sistem, Borsa İstanbul (BIST) hisselerini analiz etmenin yanı sıra kasanızı ve portföyünüzü (elinizdeki hisseleri) yönetmenize olanak tanır.

## 1. İlk Kurulum (Windows için)
1. **Python Yüklemesi:** [python.org](https://www.python.org/downloads/windows/) üzerinden en güncel Python sürümünü indirin. Yüklerken alttaki **"Add Python to PATH"** kutucuğunu mutlaka işaretleyin.
2. **Kütüphanelerin Yüklenmesi:** Windows arama çubuğuna `cmd` yazıp hata almamak için şu komutu tek seferde yapıştırın ve Enter'a basın:
   ```bash
   pip install streamlit yfinance plotly pandas sqlite3
   ```

## 2. Sistemi Çalıştırma
1. Dosyaların bulunduğu klasöre gidin (`c:\Users\recai\Desktop\borsa_app`).
2. Klasör içindeyken üstteki adres çubuğuna `cmd` yazıp Enter'a basın.
3. Gelen siyah ekrana şu komutu yazın:
   ```bash
   streamlit run app.py
   ```

## 🎮 Uygulama Nasıl Kullanılır?
- **Kasa Tanımlama:** Sol menüdeki "Bütçe Güncelle" alanından başlangıç paranızı girebilirsiniz (Varsayılan 10.000 TL).
- **Hisse Sorgulama:** Ana ekrandaki kutucuğa `THYAO.IS` gibi sembolü yazın.
- **Portföye Ekleme:** Bir hisseyi gerçekten aldığınızda, ekrandaki "Portföye Ekle" sekmesine gelin, adet ve fiyat girip "ALIM OLARAK KAYDET" deyin. Kasanız otomatik düşecek, hisse sol menüye eklenecektir.
- **Satış Yapma:** Elinizdeki bir hisseyi sattığınızda "Satış Yap" sekmesinden fiyatı girip onaylayın. Kâr/Zarar kasanıza otomatik eklenecektir.

## ⚡ Akıllı Sinyaller
- Bot, elinizde bir hisse varken size tekrar "AL" demez; kâr almanız veya trendi izlemeniz için **SAT** veya **TUT** der.
- Bir hisse için "AL" sinyali oluşursa, bot size kasanızın %10'u ile ne kadar almanız gerektiğini ve ertesi sabah için maksimum emir fiyatını (+%2 tolerans) otomatik hesaplar.

---
### 🆘 Destek Lazım mı?
Eğer CMD (siyah ekran) üzerinde bir hata görürseniz o metni kopyalayıp bana iletebilirsiniz. Veritabanınız (`pms_data.db`) klasörde otomatik oluşacaktır, silmeyin!

İyi analizler ve bol kârlar dilerim! 📈💼
