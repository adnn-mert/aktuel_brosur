# Aktüel Broşür Uygulaması — Plan

Bu dosya projenin tek "gerçek kaynak" belgesidir: kararlar, ilerleme ve devir notu burada tutulur.
Yalnızca yönetici model (ana oturum) yazar; `worker` bu dosyaya dokunmaz.

## 0. Kaldığın yerden devam (devir notu)

**Yeni oturuma verilecek istem:**

> `PLAN.md` ve `CLAUDE.md` dosyalarını oku. Sen bu projenin yöneticisisin: kod yazmazsın,
> kod işlerini `worker` alt ajanına (Opus 5.5, high), görünüşle ilgili işleri `designer` alt
> ajanına verir, çıktılarını denetler, düzelttirirsin. Birbirine dokunmayan işleri birden fazla
> worker ile paralel yürütebilirsin. Bölüm 5'teki ilk işaretlenmemiş adımdan devam et ve her
> kabul edilen görevden sonra Bölüm 9'daki ilerleme günlüğünü güncelle.

**Şu anki durum:** Bölüm 9'un son satırına bak.

**Kullanıcıdan beklenen işler:**
- [x] GitHub CLI kurulumu ve giriş (13 Kasım'da yapıldı; repo: https://github.com/adnn-mert/aktuel_brosur, herkese açık)
- [ ] Aşama 1I'de: Firebase projesi için hesap girişi ve şart kabulü
- [ ] Aşama 3'te: Gemini API anahtarını GitHub Secrets'a eklemek

## 1. Bağlam

Türkiye'deki marketlerin aktüel broşürlerini tek uygulamada gösteren, yaşlı kullanıcıya göre
tasarlanmış (büyük logo, büyük buton, yakınlaştırılabilir broşür) bir Flutter uygulaması.
Sunucu ve bütçe yok: veriyi zamanlanmış bir GitHub Actions işi toplar, JSON olarak yayınlar,
uygulama yalnızca o JSON'u okur. Site değişirse uygulamaya değil kazıyıcıya dokunulur.
Proje GitHub portfolyosu içindir, mağazaya konmayacak.

Çalışma düzeni: yönetici model planlar, görev verir, kontrol eder; kodu `worker` alt ajanı
(Opus 5.5, high) yazar. Fable erişimi 16 Kasım 2026'da bitiyor; sonrasında aynı düzen Opus ile
bu dosya üzerinden sürdürülür.

## 2. Alınan kararlar

| Konu | Karar |
|---|---|
| Uygulama adı | **Çarşı Pazar** (kullanıcı seçti, 13 Kasım). Görünen ad budur; klasör, repo ve paket adı teknik ad olarak `aktuel_brosur` kalır |
| Logo ve açılış | Kullanıcının fikri: kitap / broşür biçiminde bir logo. Açılışta kitabın sayfaları bir yandan öbür yana hızlıca çevrilir, birkaç saniye görünür. Uygulama notu: hareket yaklaşık 1,5–2 sn sürer, veri bu sırada arka planda yüklenir (açılışı geciktirmez), sistemde "hareketi azalt" açıksa durağan logo gösterilir |
| Klasör | `Desktop\Projects\aktuel_brosur` |
| Uygulama | Flutter 3.47 (kurulu), tek kod tabanı; test `Medium_Phone` Android emülatöründe |
| iOS | Kod iOS'a uygun yazılır, cihaz testi yok (Mac yok) |
| Veri toplama | Python kazıyıcı, GitHub Actions'ta günde 3 kez |
| Sayfa görselleri | Hibrit: görsel veren markette doğrudan marketin adresi; yalnızca PDF verende kazıyıcı sayfaları WebP'ye çevirip GitHub'da tutar |
| Arşiv | Geçerli + yaklaşan broşürler üstte, altında son 4 hafta |
| Aşama 1 ekstraları | İnternetsiz okuma, favori marketler, yeni broşür bildirimi (Firebase push) |
| Fiyat | Fiyatı yazı olarak veren marketler için ürün/fiyat bölümü ve arama erken gelir; görsel broşürler için Gemini OCR önce ölçülür, sonra karar verilir |
| Watsons | Aşama 1'de: ana site engelli ama katalog `katalog.watsons.com.tr` adresinde açık (Publitas) |
| CarrefourSA, Gratis | Kazınmaz; marketin kendi katalog görüntüleyicisi uygulama içinde açılır |
| A101 | Web görünümü (kullanıcı kararı, 13 Kasım): A101'in servisi GitHub Actions adreslerine 403 dönüyor, engel dolanılmıyor. Uygulama `https://www.a101.com.tr/afisler` sayfasını içeride açar. A101 ayrıştırıcısı yazılmaz |
| Arayüz / deneyim | `designer` alt ajanı (Fable 5.2, high) tasarlar ve uygular; tasarım sistemi `app/DESIGN.md` içinde belgelenir |
| Paralel çalışma | Dosyaları çakışmayan görevler birden fazla Opus 5.5 high worker ile aynı anda yürütülebilir |
| Engel aşma | Yapılmaz. Bot engeli koyan sitenin engeli dolanılmaz; o market ya web görünümüyle açılır ya da listeye girmez |
| Aracı siteler | Akakçe vb. derleyicilerden içerik alınmaz |

## 3. Araştırma özeti (13 Kasım 2026, gerçek isteklerle doğrulandı)

| Market | Kaynak | Format | Tarih bilgisi | Zorluk |
|---|---|---|---|---|
| BİM | `bim.com.tr/Categories/680/afisler.aspx` + aktüel sekmeleri | JPG afiş (940×1409) + HTML ürün kartı (ad, fiyat) | Başlık metni, yılsız | Kolay |
| A101 | `rio.a101.com.tr/.../poster/list` ve `poster/get/<id>` | WebP sayfa (1127×1690), JSON | Sayfa başına `start`/`end` | Kolay, belgesiz servis |
| Şok | `kurumsal.sokmarket.com.tr/tr/firsatlar` | Vektör PDF (8 sayfa, 22 MB) | Kart metni + dosya adı | Kolay |
| Migros, 5M | `money.com.tr/migroskop-dijital` + `migroskop.migros.com.tr` | Güncel sayı: HTML ürün kartı (ad, fiyat) + 716×1024 görsel; PDF iki hafta sonra | `mcdate` özniteliği | Kolay |
| Macrocenter | `money.com.tr/macrostyle-dijital` | Aylık PDF (5 MB) | `mcdate` | Kolay |
| bonVeno | `bonveno.com.tr/Kampanyalarimiz` | Haftalık tek sayfa vektör PDF (1,4 MB) | Yalnızca dosya adı | Kolay |
| Hakmar | `hakmar.com.tr/indirim/` | JPG sayfa (1825×2560) | Başlık + dosya adı | Kolay |
| Tarım Kredi | `tkkoop.com.tr/haftalik-kampanyalar/...` | HTML ürün kartı + PDF (17 MB) | Başlık + dosya adı | Kolay, site ~20 sn yavaş |
| Rossmann | `rossmann.com.tr/kataloglar` → `katalog.rossmann.com.tr/.../Image.ashx` | JPG sayfa (1149×1609) | Yalnızca ay | Kolay |
| Metro | `brosurler.metro-tr.com/<slug>/spreads.json` (Publitas) | JPG sayfa (1800×3200) + sayfa metni | Yok; başlıktan | Orta: yeni broşür adresini bulmak zor |
| Watsons | `katalog.watsons.com.tr/` (kök adres güncel kataloğa gider) → `<slug>/spreads.json` (Publitas) | JPG sayfa (2400 px'e kadar), aylık, 46 sayfa | Yok; başlıktaki ay | Kolay; Metro ile aynı uyarlayıcı |
| Gratis | `gratis.com/gratis-katalog` | FlipHTML5 görüntüleyici, sayfa listesi şifreli | Yalnızca ay | Web görünümü |
| CarrefourSA | `carrefoursa.com/kataloglar` | FlipHTML5, sayfalar şifreli paket; güvenlik duvarı engelliyor | Sayfa metni | Web görünümü |
| File Market | — | Broşür yayınlamıyor | — | Kapsam dışı |

Sonraya aday (yalnızca sayfalarının varlığı görüldü): Onur Market, Bizim Toptan, Mopaş.

### Kaynak ayrıntıları (kazıyıcı yazarken gerekenler)

- **BİM:** `afisler.aspx` tek istekte tüm güncel afişleri verir; tam boy adres `data-bigimg` özniteliğinde (`cdn1.bim.com.tr/uploads/afisler/<uuid>.jpg`), küçük hali `k_` önekli. Tarih başlıkları "13 Kasım Cuma", "13-19 Kasım" gibi, yıl yok. Ürün kartları `aktuel-urunler.aspx?Bim_AktuelTarihKey=<id>` sekmelerinde; fiyat lira ve kuruş ayrı. Yeni setler Salı, Çarşamba, Cuma, Pazar.
- **A101:** `https://rio.a101.com.tr/dbmk89vnr/CALL/poster/list/default?__culture=tr-TR&__platform=web` liste; `.../poster/get/default/<id>?...` sayfalar. Görsel adresi `..._3840x3840.png` soneki ile en büyük hali verir (içerik WebP). Afiş kimlikleri sabit yuvadır, içerik yerinde değişir: broşür kimliği sayfa görseli kimliklerinden türetilmeli, geçerlilik sayfa `start`/`end` alanlarından alınmalı. `www.a101.com.tr` kullanılmaz (Cloudflare engeli).
- **Şok:** `bc-aktual-card` blokları; PDF `/uploads/pdf/<rastgele>-18-24kasim.pdf`. PDF sayfaları kazıyıcıda WebP'ye çevrilir.
- **Migros / 5M / Macrocenter:** `money.com.tr` sayfalarında `<button class="_df_button" source="…pdf" mcdate="1 - 30 Kasım 2026">`. Migroskop güncel sayısında PDF yok; `migroskop.migros.com.tr/migroskop` (5M: `/5m-migroskop`) sayfasında `div.product` kartları (`h1.title`, bölünmüş fiyat, `small.stock-info`). Tarih yalnızca money.com.tr'de. Migros Jet ve Piknik-Bahçe güncel değil, alınmaz.
- **bonVeno:** `/Kampanyalarimiz` içinde `/katalog/` altındaki `.pdf` bağlantıları; tarih dosya adında ("13-19KASIM").
- **Hakmar:** WordPress sayfasında `wp-content/uploads/2026/11/10-23-KASIM-2026_Insert-1-8-scaled.jpg`.
- **Tarım Kredi:** ürün kartları + ana sayfadaki "BÜLTENİ İNDİR" PDF'i; uzun zaman aşımı gerekir.
- **Rossmann:** `/kataloglar` içindeki iPaper iframe adresleri → `katalog.rossmann.com.tr/2026/11-kasim/<slug>/`; sayfa `…/Image.ashx?PageNumber=N&ImageType=Zoom` (kalıcı adres, imzalı CDN adresine yönlendirir). Uygulamaya `Image.ashx` adresi verilir.
- **Publitas (Metro, Watsons):** `<slug>/data.json` (`numPages`, `cacheToken`), `<slug>/spreads.json` (sayfa görselleri `at200`…`at2400`, göreli yol; kök `https://view.publitas.com`). Metro haftalık broşürü aynı slug'ı yeniden kullanır: değişiklik `cacheToken` ile anlaşılır. Watsons'ta kök adres ve `sitemap.xml` güncel kataloğu gösterir.

Plana yansıyan sonuçlar:
- Üç farklı broşür türü var: **sayfa** (görsel), **ürün listesi** (ad + fiyat), **web görünümü**. Veri modeli ve uygulama üçünü de taşır.
- BİM afişi 940 px; yakınlaştırınca yumuşar. BİM'de afişin yanında ürün listesi de gösterilir.
- Yerel erişim testleri tam güvenilir değil (PC'nin çıkışı Cloudflare tünelinden görünüyor). GitHub Actions sunucularından erişim Aşama 0'da ayrıca denenir.
- Fiyat karşılaştırması için resmi `marketfiyati.org.tr` servisi (Migros, Carrefour, Şok, Tarım Kredi, A101, Hakmar, BİM) yanıt veriyor ama belgesiz; Aşama 5'te değerlendirilir.

## 4. Mimari

```
aktuel_brosur/
  PLAN.md                  kararlar + ilerleme + devir notu (yalnızca yönetici model yazar)
  CLAUDE.md                kısa kurallar, PLAN.md'ye işaret
  .claude/agents/worker.md kod yazan alt ajan (Opus 5.5, high)
  schema/catalog.schema.json
  scraper/                 Python 3.13
    core/                  http (hız sınırı, tekrar deneme), tarih ayrıştırma, pdf→webp, model, yayın
    sources/               bim.py, a101.py, sok.py, ... (market başına bir dosya)
    tests/fixtures/        kaydedilmiş HTML/JSON örnekleri (testler ağa çıkmaz)
  app/                     Flutter
    lib/data/              modeller, depo (ağ + önbellek)
    lib/features/          home, chain, viewer, products, favorites, settings
  .github/workflows/       scrape.yml, ci.yml, probe.yml
```

**Yayın:** kazıyıcı çıktısı ayrı bir `data` dalına tek commit olarak (geçmiş birikmeden) yazılır ve
GitHub Pages ile sunulur. İçerik: `catalog.json`, `products/<brosur_id>.json`, `health.json`,
`media/<market>/<brosur_id>/p01.webp` (yalnızca PDF'ten çevrilen sayfalar, ~1600 px genişlik).
Süresi dolalı 4 haftayı geçen broşürler ve görselleri her çalışmada silinir.

**catalog.json (özet):**
- kök: `schema_version`, `generated_at`, `min_app_version`, `chains[]`, `brochures[]`
- `chain`: `id`, `name`, `country` ("TR"; Avrupa için baştan var), `kind` (scraped | webview), `web_url`, `status` (ok | stale), `last_ok_at`
- `brochure`: `id` (kararlı), `chain_id`, `title`, `date_label` (özgün metin), `valid_from`, `valid_to` (boş olabilir), `kind` (pages | products | both), `cover`, `pages[]` {url, w, h}, `products_url`, `source_url`, `first_seen`
- `product` (ayrı dosyada): `name`, `brand`, `quantity_text`, `price`, `old_price`, `image`, `page_index`

**Dayanıklılık kuralları:**
- Her kaynak ayrı çalışır; biri bozulursa o marketin son iyi verisi korunur, `status: stale` olur, diğerleri etkilenmez.
- Çıktı şemaya uymuyorsa yayınlanmaz. Boş sonuç "broşür yok" sayılmaz, hata sayılır.
- Bir kaynak art arda başarısız olursa iş kırmızıya düşer (GitHub e-posta atar).
- Kazıyıcı kendini dürüstçe tanıtır, alan adı başına saniyede en fazla 1 istek atar.

**Uygulama ekranları:**
1. **Ana ekran:** 2 sütun büyük logo kartları, favoriler üstte. Menü yok.
2. **Market ekranı:** "Bu hafta", "Gelecek hafta", "Geçmiş" başlıkları altında kapak + tarih ("13–19 Kasım").
3. **Broşür görüntüleyici:** iki parmak + çift dokunma ile yakınlaştırma, ayrıca görünür **+ / −** düğmeleri, büyük ileri/geri okları, "3 / 8" sayfa göstergesi.
4. **Ürün listesi:** büyük yazılı ürün kartları (ad, miktar, fiyat); Migros ve BİM için.
5. **Web görünümü:** Gratis ve CarrefourSA'nın kendi katalog sayfası uygulama içinde.

Tasarım ilkeleri: dokunma hedefi en az 56 dp, yazı en az 18 sp, yüksek kontrast, sistem yazı
büyütmesine uyum, ekran okuyucu etiketleri. Metinler baştan çeviri dosyasında (Avrupa için hazırlık).

Paketler: `flutter_riverpod`, `http`, `cached_network_image` + `flutter_cache_manager`,
`photo_view`, `shared_preferences`, `webview_flutter`, `firebase_messaging`.
Kazıyıcı: `httpx`, `selectolax`, `pymupdf`, `pillow`, `jsonschema`, `pytest`.

## 5. Aşamalar

### Aşama 0 — Kurulum ve erişim denemesi
- [x] 0.1 Klasör, `git init`, PLAN.md, CLAUDE.md, `.claude/agents/worker.md`
- [x] 0.2 GitHub CLI + giriş; herkese açık repo oluşturuldu. Bu depoda commit'ler GitHub'ın gizli e-posta adresiyle atılır (depo düzeyinde `git config user.email`); kişisel e-posta repoya girmez.
- [x] 0.3 `probe.yml` Actions'ta çalıştırıldı (13 Kasım, çalışma 43430207929). Dürüst `User-Agent` ile 13 kaynağın 12'si 200 ve beklenen içerikle döndü: BİM, Şok, Migros (liste + görüntüleyici), Macrocenter, bonVeno, Hakmar, Tarım Kredi, Rossmann, Metro, Watsons, Gratis. Yalnızca A101 `403 {"message":"Permission denied"}`.
- **Karar kapısı sonucu:** A101 web görünümüne alındı; diğer bütün kaynaklar Actions'tan kazınabilir, PC'de zamanlanmış göreve gerek kalmadı.

### Aşama 1 — Türkiye'de çalışan broşür uygulaması
- [x] 1A Veri sözleşmesi: şemalar, örnekler, modeller, doğrulama, tarih ayrıştırma, kimlik, istek katmanı (172 test)
- [x] 1B Kazıyıcı çekirdeği (çalıştırma hattı, kaynak yalıtımı, önceki durumla birleştirme, PDF→WebP, budama) + BİM ve Şok kaynakları + fixture testleri (255 test; yeni kaynak ekleme kılavuzu `scraper/sources/README.md`)
- [x] 1C `scrape.yml` (günde 3 kez: TR 06:17, 12:17, 18:17), `data` dalına tek commit yayın (`scraper/publish.py`), GitHub Pages, `health.json`, `ci-scraper.yml` + `ci-app.yml`. Yayın adresi: `https://adnn-mert.github.io/aktuel_brosur/` (`catalog.json`, `health.json`, `products/`, `media/`)
- [x] 1D-veri (worker) Flutter projesi + veri katmanı: modeller, depo (ağ + önbellek + örnek veri), sağlayıcılar, favori deposu (80 test; kılavuz `app/lib/data/README.md`)
- [x] 1D-arayüz **TAMAM (14 Kasım, commit d6766fb)**: aşağıdaki kapsamın hepsi yazıldı, 79 arayüz testi, 25 ekran görüntüsü `app/design/screenshots/`, tasarım sistemi `app/DESIGN.md`. Favoriler, internetsiz okuma (45 gün görsel önbelleği) ve web görünümü (1G, 1H) de bu işte yapıldı. Özgün kapsam: Tasarım sistemi + logo (kitap) ve sayfa çevirme açılış hareketi + uygulama simgesi + ana ekran, market ekranı, broşür görüntüleyici, ürün listesi, web görünümü, boş/hata durumları; `app/DESIGN.md`
- [x] 1E Migros (Migroskop, fiyatlı ürün kartları) ve Macrocenter (aylık MacroStyle PDF) kaynakları; BİM ürünleri 1B'de yapılmıştı. 5M Migroskop yayınlanmıyor (ürünleri Migroskop ile birebir aynı). Sürüyor: Money üyelik fiyatı alanı (W6b + W5b), ardından ürün kartında gösterimi (designer D2)
- [ ] 1F Kalan kaynaklar: Hakmar, bonVeno, Macrocenter, Rossmann, Tarım Kredi, ortak Publitas uyarlayıcısı ile Metro ve Watsons
- [x] 1G Favoriler, internetsiz okuma, erişilebilirlik (D1 içinde yapıldı). Kalan: iki parmakla yakınlaştırmanın gerçek cihazda elle denenmesi (emülatörde üretilemiyor, yalnızca widget testi var)
- [x] 1H Web görünümü marketleri: A101, Gratis, CarrefourSA (D1 içinde yapıldı; A101 ve CarrefourSA emülatörde denendi)
- [ ] 1I Firebase bildirimi: favori market başına konu aboneliği; kazıyıcı yeni broşür bulunca gönderir
- [ ] 1J README, ekran görüntüleri, Actions ile APK (GitHub Releases); isteğe bağlı imzasız iOS derleme denemesi

### Aşama 2 — Broşürlerde ara (yapay zekâsız)
Fiyatı yazı olarak veren marketlerin (BİM, Migros, Tarım Kredi, Metro, Rossmann) ürünleri tek
`search.json`'da toplanır. Kullanıcı ürün adı yazar, sonuçlar fiyat sırasıyla çıkar, dokununca
ilgili broşüre gider. Fiyat marketin kendi yazdığı fiyattır; eşleştirme yapılmaz.

### Aşama 3 — OCR ölçümü (Gemini)
- Önce ölçüm: BİM afiş görselleri modele okutulur, sonuç BİM'in kendi yazılı fiyatlarıyla otomatik karşılaştırılır (elle etiketleme gerekmez). Model adı ve fiyatı o gün resmi belgeden doğrulanır (kullanıcının önerdiği: Gemini 3.8 Flash).
- **Karar kapısı:** fiyat doğruluğu eşiğin (öneri: %98) altındaysa OCR fiyatı gösterilmez. Üstündeyse A101, Şok, Hakmar aramaya eklenir; her OCR fiyatı "broşürden okundu" etiketi ve broşür sayfası bağlantısıyla gösterilir.
- API anahtarını GitHub Secrets'a kullanıcı ekler; anahtar sohbete ve repoya girmez.

### Aşama 4 — Avrupa ve Amerika
Ülke seçimi, ülke başına market listesi (Almanya: Aldi, Lidl, Kaufland ile başlanır). Her ülke için
önce Aşama 0'daki gibi site araştırması yapılır.

### Aşama 5 — "Ne nerede ucuz"
Gerçek ürün eşleştirme: barkod (A101 veriyor), `marketfiyati.org.tr`, birim fiyat. En son.

## 6. Çalışma döngüsü

1. Yönetici model görevi yazar: amaç, dokunulacak dosyalar, kabul ölçütleri, geçmesi gereken testler.
2. `worker` uygular, `pytest` / `flutter analyze` / `flutter test` çalıştırır, rapor verir.
3. Yönetici farkı okur, testleri kendisi yeniden çalıştırır, uygulamayı emülatörde açıp ekran görüntüsüne bakar.
4. Eksik varsa aynı worker'a düzeltme gönderilir; kabul edilince commit atılır, bu dosyanın ilerleme günlüğü güncellenir.

`worker` türü oturumda görünmüyorsa (oturum başka klasörde açıldıysa) aynı talimat, model Opus ve
çaba high verilerek genel ajana gönderilir; ajan önce `.claude/agents/worker.md` ve `CLAUDE.md` okur.

**Kullanım sınırı notu:** 13 Kasım'da iki paralel Opus worker + yönetici, 5 saatlik kullanım sınırını
doldurdu ve iki worker yarıda kesildi (sıfırlanma 20:10). Kesilen worker yeniden başlatılmaz; aynı
ajana "kaldığın yerden devam et" mesajı gönderilir, önce diskteki durumu okur. Öncelik sırası sınır
daralınca şöyledir: (1) Fable tasarımcı işi (16 Kasım'a kadar tek fırsat), (2) uygulamanın veri katmanı,
(3) kazıyıcı kaynakları. Aynı anda en fazla iki ajan çalıştırılır; tasarımcı çalışırken yanına en çok
bir Opus worker verilir. 14 Kasım güncellemesi: sınır ikinci kez dolduğu için tasarımcı işi (D1)
bitene kadar yanında başka ajan çalıştırılmaz; yönetici de bu sürede yalnızca denetim yapar.

**Oturum yenileme kuralı (kullanıcı isteği, 14 Kasım):** uzun oturumda her tur bütün geçmişi yeniden
işler; 400 bin token'lık oturumda yöneticinin tek bir turu 5 saatlik sınırın yaklaşık %40'ını yedi.
Bu yüzden yönetici, aşağıdaki noktalardan birine gelindiğinde ve **çalışan alt ajan kalmadığında**
kullanıcıya açıkça "yeni oturuma geçme zamanı" der ve Bölüm 0'daki istemi verir:
1. Bir görev grubu kabul edilip commit edildiğinde ve ilerleme günlüğü güncellendiğinde (asıl an budur).
2. Oturum bağlamı yaklaşık 150 bin token'ı geçtiğinde.
3. Yeni bir aşamaya ya da alt aşamaya başlamadan önce.
4. Kullanım sınırı dolup iş kesildiğinde, kesilen ajanların işi bitirilip commit edildikten sonra.
Çalışan ajan varken oturum değiştirilmez (yeni oturum onlara "devam et" diyemez; yarım iş diskte
kalır ama bağlamı kaybolur). Oturum değişmeden önce yönetici: çalışma kopyasını temiz bırakır
(kabul edilen her şey commit + push), Bölüm 9'a "sırada ne var" satırını yazar. Yeni oturum
`aktuel_brosur` klasöründe açılır (böylece `worker` ve `designer` ajan türleri tanınır). Yönetici
turlarını az ve dolu tutar: ara durum mesajı için tur harcamaz, denetim + commit + sonraki görevi
aynı turda yapar. Git dalı ya da oturum çatallama kullanılmaz: tek kişilik projede `main` + CI yeterli,
çatallanan oturum ise bütün geçmişi taşıdığı için sınır açısından hiçbir şey kazandırmaz.

**Model seçimi (kullanıcı kararı, 14 Kasım):** her işi Opus'a vermek zorunlu değil; alt ajanın modelini
yönetici seçer (Pro planda sınır sık doluyor). Uygulanan ölçüt: kalıbı kurulmuş, fixture + test ile
korunan ve yöneticinin denetlediği işler (yeni market kaynağı, küçük düzeltme, belge) Sonnet 5.5 ile;
temel / incelikli işler (hat mimarisi, fiyatla ilgili kararlar, bildirim altyapısı) Opus 5.5 ile;
görünüş işleri Fable ile. Sonnet bir işte takılırsa erken müdahale kuralı işler: iş Opus'a ya da
yöneticiye geçer.

**Erken müdahale kuralı (kullanıcı isteği, 13 Kasım):** worker bir işte takılırsa yönetici model
beklemez, işi devralır. Ölçüt: worker "yapamadım / engellendim" diye rapor verirse, bir düzeltme
turundan sonra kabul ölçütleri hâlâ karşılanmıyorsa, aynı hata ikinci kez dönerse ya da worker
sorunu dolanmak için kapsamı daraltıp testi gevşetirse. Devralınan parça dar tutulur (yalnızca
takılan kısım), nedeni ve çözümü ilerleme günlüğüne yazılır. Fable erişimi bittikten sonra aynı
kural, takılan işi yeni bir worker'a temiz bir özetle vermek biçiminde uygulanır.

**Arayüz işleri:** görünüşle ilgili her görev `designer` ajanına (Fable 5.2, high) gider; veri katmanı
ve kazıyıcı `worker`'da kalır. Dosya sınırı: designer `app/lib/design/`, `app/lib/features/`,
`app/lib/l10n/`, `app/assets/`, `app/DESIGN.md`; worker `app/lib/data/`, `scraper/`, `schema/`,
`.github/`. Fable erişimi 16 Kasım 2026'da bittiği için arayüz işleri öne alınır: o tarihe kadar
tasarım sistemi ve bütün ana ekranlar (ana ekran, market, görüntüleyici, ürün listesi, web görünümü,
boş/hata durumları) tamamlanmalı. Sonrasında arayüze dokunan model `app/DESIGN.md`'ye uyar; büyük
görsel kararlar için kullanıcıya sorulur.

**Zor site incelemesi:** Fable erişimi sürdüğü sürece yapısı karışık siteler Fable 5.2 (high) ile
incelenir; 16 Kasım'dan sonra Opus ile.

**Firebase adımı:** proje kullanıcının Google hesabında, kullanıcının tarayıcısında yönetici model
tarafından kurulur; hesap girişi, şart kabulü ve gizli anahtarın GitHub'a eklenmesi adımlarında
durulup kullanıcıya sorulur ya da tek satırlık komut kullanıcıya verilir.

## 7. Doğrulama

- Kazıyıcı: `pytest` (fixture'larla, ağsız) + `python -m scraper run --only <market> --dry-run` canlı deneme + şema doğrulaması.
- Yayın: Actions çalışması yeşil, Pages adresinden `catalog.json` iniyor, sayfa görseli adresleri 200 dönüyor.
- Uygulama: `flutter analyze` temiz, `flutter test` geçiyor, emülatörde uçtan uca akış: market seç → hafta seç → broşürü aç → yakınlaştır; uçak modunda daha önce açılan broşür yine açılıyor.
- Dayanıklılık: bir kaynağın fixture'ı bozularak "son iyi veri korunuyor, diğerleri etkilenmiyor" testi.

## 8. Riskler

| Risk | Önlem |
|---|---|
| Actions sunucuları Türk sitelerince engellenir | Aşama 0 denemesi; yedek: PC açılınca çalışan görev |
| A101'in belgesiz servisi değişir | Kaynak yalıtımı, `stale` durumu, kırmızı iş uyarısı |
| Metro'da yeni broşür adresi bulunamaz | Bilinen adresler + site haritası; bulunamazsa Metro web görünümüne alınır |
| Telif | Yalnızca PDF'ten çevrilen sayfalar repoda; 4 hafta sonra silinir; şikâyet gelirse o market web görünümüne alınır |
| 60 gün hareketsizlikte zamanlanmış iş durur | `data` dalına düzenli commit; yine de izlenir |
| Fable erişimi 16 Kasım'da biter | Bu dosyadaki devir notu ve güncel ilerleme günlüğü |

## 9. İlerleme günlüğü

- 2026-11-13: Site araştırması tamamlandı, kararlar alındı, plan onaylandı.
- 2026-11-13: Watsons kataloğunun Publitas'ta açık olduğu doğrulandı, Aşama 1'e alındı. CarrefourSA'nın iki katmanlı korumalı olduğu doğrulandı, web görünümünde kaldı.
- 2026-11-13: 0.1 tamam (klasör, git, PLAN.md, CLAUDE.md, worker.md). Sırada: 1A veri sözleşmesi + 0.3 deneme işi (worker'da). 0.2 kullanıcıyı bekliyor.
- 2026-11-13: Kullanıcı kararı: arayüz/deneyim işleri Fable 5.2 high `designer` ajanında, paralel Opus worker'lara izin var. `designer.md` yazıldı. Arayüz işleri 16 Kasım'dan önceye alındı. W1 (1A + 0.3) ve W2 (1D-veri) paralel yürüyor.
- 2026-11-13: Uygulama adı "Çarşı Pazar" seçildi; logo fikri (kitap + açılışta sayfa çevirme) karara bağlandı.
- 2026-11-13: 0.2 tamam: repo oluşturuldu ve `main` gönderildi. Sırada: W1 kabul edilince gönder, `probe.yml`'i Actions'ta çalıştır (0.3 karar kapısı).
- 2026-11-13: Erken müdahale kuralı eklendi (Bölüm 6).
- 2026-11-13: W1 kabul edildi (1A tamam, commit 4a6d374). 0.3 tamam: Actions'tan 12/13 kaynak açık, A101 403. Kullanıcı A101 için "yalnızca web görünümü" seçti. Not: `schema/examples/catalog.example.json` içinde A101 hâlâ kazınan zincir olarak duruyor; W3 düzeltecek, uygulamadaki örnek veri de eşitlenecek. Sırada: W3 (1B: çekirdek + BİM + Şok) başladı, W2 (1D-veri) sürüyor.
- 2026-11-13 20:11: W2 ve W3 kullanım sınırına takılıp kesildi; sınır sıfırlanınca ikisi de kaldığı yerden sürdürüldü. Kesildiği andaki durum: W2 `app/lib/data/` (modeller, depo, sağlayıcılar, gruplama), yer tutucu ekranlar ve l10n'i yazmış, testler ve README eksik, hiçbiri commit edilmedi (`app/` izlenmiyor). W3 diske henüz bir şey yazmamıştı. Sırada: W2 raporu gelince denetle → commit → `designer`'ı başlat.
- 2026-11-13 20:40: W2 kabul edildi (1D-veri tamam, commit 3ceea86): analiz temiz, 80 test, debug APK derlendi. Not: bu makinede Gradle `Unable to establish loopback connection` hatası verirse komut `JAVA_TOOL_OPTIONS=-Djdk.net.unixdomain.tmpdir=<kısa geçici klasör>` ile çalıştırılır. D1 (`designer`, Fable high: tasarım sistemi + bütün ekranlar + logo/açılış) başlatıldı; ilerlemesini `app/DESIGN.md` "Durum" bölümüne yazıyor. W3 (1B) sürüyor. Açık nokta: veri katmanındaki "…'dan itibaren / …'a kadar" metinleri kodda sabit, Avrupa aşamasında çeviri dosyasına taşınacak.
- 2026-11-13 21:05: W3 kabul edildi (1B tamam, commit f687efc). Canlı çalışma: BİM 19 broşür (afiş + fiyatlı ürün kartları), Şok 2 broşür (PDF → WebP); ikinci çalışmada PDF yeniden inmiyor. Şok sayfasına bakıldı: 1600 px'te okunur, derin yakınlaştırma için 2000 px'e çıkarılıyor. Kararlar: `last_ok_at` gerçek son başarılı çalışma zamanı olarak kalır; BİM tek günlük aktüel broşürleri başlangıç + 6 gün geçerli sayılır (yoksa ertesi gün "Geçmiş"e düşüyor); bildirim adımı `RunReport.first_run` iken göndermez. W4 başladı (aynı worker): bu iki düzeltme + 1C (`scrape.yml`, `data` dalına tek commit yayın, `ci.yml`). W4 kabul edilince yönetici: gönder → `scrape.yml`'i elle tetikle → Pages'i `data` dalından aç → uygulamayı `CATALOG_BASE_URL=https://adnn-mert.github.io/aktuel_brosur/` ile dene. Sonraki veri katmanı isteği (designer bitince): "Bu hafta" bölümünde sıralama en yeni başlangıç önce olsun (BİM'de çok sayıda geçerli broşür var).
- 2026-11-14 01:12: Kullanım sınırı ikinci kez doldu (20:10–01:10 penceresi); D1 ve W4 kesildi, sıfırlanınca ikisi de aynı ajana mesajla sürdürüldü. Kesinti anında: D1 yalnızca 1. dilimin bir kısmını yazmıştı (`app/lib/design/` belirteçler, tema, tipografi, logo bileşeni; yazı tipleri; market logoları; örnek veri gerçek adreslerle güncellendi) — `app/DESIGN.md` ve ekranlar henüz yok, hiçbiri commit edilmedi. W4 kodu ve testleri bitirmişti (282 test), yalnızca canlı doğrulama ve rapor kalmıştı; o da commit edilmedi. Karar: W4 bitince yeni Opus worker başlatılmaz; sınır tasarımcıya kalsın diye D1 tek başına çalışır. Kalan kazıyıcı kaynakları (1E, 1F) D1 bitince ya da 16 Kasım'dan sonra yapılır.
- 2026-11-14 01:25: W4 kabul edildi (1C tamam, commit 74b05c6; 282 test). `scrape.yml` elle tetiklendi (çalışma 43517580951, başarılı): `data` dalı tek commit ile oluştu, Pages `data` dalından açıldı, `catalog.json` (BİM 19 + Şok 2 broşür), bir Şok sayfası (2000×2882 WebP) ve ETag başlığı canlı adresten doğrulandı. `ci-scraper.yml` yeşil. **Doğrulanacak:** zamanlanmış çalışmanın `GITHUB_TOKEN` ile yaptığı push'un Pages'i yeniden derletip derletmediği (14 Kasım 06:17 TR çalışmasından sonra `catalog.json` içindeki `generated_at` değerine bak; değişmediyse yayın `actions/deploy-pages` tabanlı hâle getirilir). Uygulamayı canlı veriyle açmak için: `flutter run --dart-define=CATALOG_BASE_URL=https://adnn-mert.github.io/aktuel_brosur/`. Sırada: yalnızca D1 (designer) çalışıyor; bitince denetim + ekran görüntüleri.
- 2026-11-14 06:12: Kullanım sınırı üçüncü kez doldu (01:10–06:10 penceresi), D1 kesildi ve sıfırlanınca sürdürüldü. D1'in durumu (`app/DESIGN.md` "Durum" tablosundan): belirteçler/tema/yazı tipleri/logolar, temel bileşenler, ana ekran ve market ekranı bitti ve emülatörde bakıldı; açılış hareketi yazıldı ama izlenmedi; broşür görüntüleyici, ürün listesi ve web görünümü yarım; arayüz testleri ve ekran görüntüleri yok. Hiçbiri commit edilmedi (`app/` altında çalışma kopyasında). Pages yeniden derleme kontrolü hâlâ bekliyor (06:17 çalışması henüz olmadı).
- 2026-11-14 11:20: **D1 kabul edildi** (commit d6766fb): analiz temiz, 159 test (80 veri + 79 arayüz) yönetici tarafından yeniden çalıştırıldı, `ci-app.yml` GitHub'da yeşil, ekran görüntülerine bakıldı (ana ekran, görüntüleyici, açılış). Ekran görüntüleri depo şişmesin diye PNG'den WebP'ye çevrildi (19 MB → 2,9 MB). Tasarımcının kapsam dışı üç işi kabul edildi: `INTERNET` izni (gerekli), derleme için `C:\Users\Public\uds` klasörü, logo indirmede zincir başına 2–3 istek. Derleme komutu: `JAVA_TOOL_OPTIONS=-Djdk.net.unixdomain.tmpdir=C:\Users\Public\uds`.
- 2026-11-14 11:20: Pages kontrolü: elle tetiklenen çalışmada (43574661618) `GITHUB_TOKEN` ile yapılan push Pages'i yeniden derletti, canlı `generated_at` güncellendi → yayın yöntemi değişmeyecek. **Açık sorun:** 14 Kasım 03:17 UTC zamanlanmış çalışması hiç başlamadı (yalnızca elle tetiklenenler var). 09:17 ve 15:17 UTC çalışmalarına bakılacak; onlar da yoksa cron ifadesi / deponun zamanlama kaydı incelenir.
- 2026-11-14 11:20: Tasarımcının veri katmanı istekleri iki worker'a verildi. W5 (`app/`): "Bu hafta" sırası en yeni başlayan üstte + arayüzdeki geçici sıralamanın silinmesi, gün değişince / uygulamaya dönünce saat ve katalog yenileme. W6 (`scraper/`): zincir renkleri, yeni zincirde `first_seen` kuralı, BİM kapak ölçüleri, Migros + 5M + Macrocenter kaynakları (1E). Sonra W7: Publitas uyarlayıcısı (Watsons, Metro; sayfa `at2400`, kapak `at600`) + Hakmar, bonVeno, Rossmann, Tarım Kredi (1F).
- 2026-11-14 11:25: W5 kabul edildi (182 test, analiz temiz): "Bu hafta" sırası veri katmanında en yeni başlayan üstte, arayüzdeki geçici sıralama silindi; uygulama öne gelince ve gece yarısında gün yenileniyor, 30 dakikadan eski katalog sessizce yenileniyor (`app/lib/data/freshness.dart`, `app/lib/features/app/data_refresher.dart`). Emülatörde elle denenmedi, widget testleriyle doğrulandı. W6 sürüyor.
- 2026-11-14 11:40: W6 kabul edildi (commit e20ce00, 341 test): Migros (242 ürün, sayı 910, 5–18 Kasım), Macrocenter (12 sayfa, 2000×2829), zincir renkleri, bir zincirin ilk çalışmasında `first_seen` geçerlilik başlangıcına çekilir ve `new_brochure_ids`'e girmez, BİM kapak ölçüleri. Yönetici kararları: (1) **Money fiyatı** raf fiyatının yerine değil, etiketli ikinci fiyat olarak gösterilecek → ürün şemasına isteğe bağlı `member_price_minor` + `member_price_label` ("Money ile"); `schema_version` 1 kalır. Migros'ta 242 ürünün 172'sinde Money fiyatı var. (2) **5M yayınlanmayacak** (Migroskop ile aynı ürünler). (3) `quantity_text` yalnızca kilogram fiyatlı ürünlerde "kg fiyatı", diğerlerinde null; stok yazıları yazılmaz. (4) Fiyatsız, yalnızca indirim rozetli 21 kart atlanmaya devam eder. W6b (kazıyıcı) ve W5b (uygulama modeli) paralel başladı; ikisi bitince D2 (designer): ürün kartında üyelik fiyatı. Zamanlanmış çalışma 08:35 UTC itibarıyla hâlâ hiç başlamadı.
- 2026-11-14 13:25: **Zamanlama doğrulandı:** ilk `schedule` çalışması 10:19 UTC'de başladı (planlanan 09:17; GitHub yaklaşık bir saat geciktirdi), başarılı, canlı `generated_at` güncellendi. 03:17 UTC çalışması atlanmıştı; yeni depolarda ilk zamanlama için olağan. Zamanlama sorunu kapandı; GitHub'ın bir saate varan gecikmesi normal kabul edilir. W5b kabul edildi (commit f3456aa, 199 test): `Product.memberPrice` / `memberPriceLabel`. Kullanım sınırı dördüncü kez doldu; D2 (designer: üyelik fiyatlı ürün kartı, "kg fiyatı" notu, uzun katalogda sayfaya atlama) ve W6b (kazıyıcı: üyelik fiyatı alanı, 5M'in kaldırılması, `quantity_text` kuralı) kesildi ve sürdürüldü; ikisinin de değişiklikleri çalışma kopyasında, commit edilmedi.
- 2026-11-14 13:35: W6b kabul edildi (commit 1185891, 361 test) ve canlıda doğrulandı: katalogda BİM 19, Şok 2, Migros 1, Macrocenter 1 broşür; Migros'ta 242 ürünün 172'sinde `member_price_minor` + "Money ile"; 5M düştü. Hatta yeni genel mekanizma: `SourceResult.retired_ids`. Worker'ın bilinçli farkı kabul edildi: iki fiyat basılı ama "MONEY'Lİ FİYAT" etiketi yoksa ürün atlanır. Not: ürün dosyasını elle doğrularken `python -m scraper validate <dosya> --type products`. Kullanıcı model seçimini serbest bıraktı (Bölüm 6). W7 (1F: Publitas ile Watsons + Metro, Hakmar, bonVeno, Rossmann, Tarım Kredi) Sonnet ile başlatıldı. D2 sürüyor.
- 2026-11-14 18:25: Kullanım sınırı beşinci kez doldu; D2 ve W7 kesildi, sıfırlanınca aynı ajanlara mesajla sürdürüldü. Kesinti anında: D2 ürün kartı / sayfaya atlama kodunu yazmış, testlere başlıyordu (ekran görüntüleri ve `app/DESIGN.md` güncellemesi kalmıştı). W7 Publitas tarafını yazmış, Hakmar ve bonVeno'yu incelemeye geçiyordu. İkisinin de değişiklikleri çalışma kopyasında, commit edilmedi. İkisine de "önce bitmiş, testi geçen dilimler" talimatı verildi.
