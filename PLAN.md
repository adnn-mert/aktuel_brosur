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
- [ ] 0.3 `probe.yml`: Actions sunucusundan her kaynağa tek istek atıp durum kodunu raporlayan deneme.
- **Karar kapısı:** Actions'tan erişilemeyen market olursa o market için yedek yol seçilir (PC açılınca çalışan zamanlanmış görev) ya da market ertelenir.

### Aşama 1 — Türkiye'de çalışan broşür uygulaması
- [ ] 1A Veri sözleşmesi: şema + elle yazılmış örnek `catalog.json`
- [ ] 1B Kazıyıcı çekirdeği + BİM, A101, Şok kaynakları + fixture testleri
- [ ] 1C `scrape.yml` zamanlama, `data` dalı, Pages yayını, `health.json`
- [ ] 1D-veri (worker) Flutter projesi + veri katmanı: modeller, depo (ağ + önbellek + örnek veri), sağlayıcılar, favori deposu
- [ ] 1D-arayüz (designer, **16 Kasım'dan önce**) Tasarım sistemi + logo (kitap) ve sayfa çevirme açılış hareketi + uygulama simgesi + ana ekran, market ekranı, broşür görüntüleyici, ürün listesi, web görünümü, boş/hata durumları; `app/DESIGN.md`
- [ ] 1E Migros, 5M, BİM ürün kaynakları (kazıyıcı tarafı)
- [ ] 1F Kalan kaynaklar: Hakmar, bonVeno, Macrocenter, Rossmann, Tarım Kredi, ortak Publitas uyarlayıcısı ile Metro ve Watsons
- [ ] 1G Favoriler, internetsiz okuma, erişilebilirlik cilası
- [ ] 1H Web görünümü marketleri: Gratis, CarrefourSA
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
