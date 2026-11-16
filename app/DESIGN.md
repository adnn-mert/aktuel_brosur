# Çarşı Pazar — tasarım sistemi

Bu belge arayüzün tek bağlayıcı kaynağıdır. Arayüze dokunan herkes (insan ya da model) önce bunu
okur, aynı dili sürdürür. Bir kural gerekçesiyle yazılmıştır; gerekçe geçersiz kalmadıkça kural
değişmez. Büyük görsel kararlar (renk, yazı tipi, logo) değiştirilmeden önce proje sahibine sorulur.

## Durum

Son güncelleme: 17 Kasım 2026. **D1, D2, D3 (ürün arama), D4 (yeni broşür bildirimi) ve 3B.3 (broşürden okunan fiyatlar) görevleri tamamlandı.**

| Dilim | Durum |
|---|---|
| 1. Belirteçler, tema (açık + koyu), yazı ölçeği, temel bileşenler | **Bitti** (`lib/design/`) |
| 2. Ana ekran | **Bitti** (`lib/features/home/`) |
| 3. Market ekranı | **Bitti** (`lib/features/chain/`) |
| 4. Broşür görüntüleyici | **Bitti** (`lib/features/brochure/`); örnek ve canlı veriyle denendi (BİM 940 px, Şok 2000 × 2882, Watsons 1960 × 2940) |
| 5. Ürün listesi | **Bitti** (`lib/features/products/`); örnek ve canlı BİM verisiyle denendi |
| 6. Web görünümü | **Bitti** (`lib/features/web/`); A101 ve CarrefourSA ile, internet varken ve yokken denendi |
| 7. Logo, açılış, uygulama simgesi, görünen ad | **Bitti** (`lib/design/widgets/logo_mark.dart`, `lib/features/splash/`, `test/tools/generate_icons_test.dart`) |
| 8. Durumlar ve cila | **Bitti**; yer tutucu klasör silindi |
| D2-1. Ürün kartında üyelik fiyatı | **Bitti** (`lib/features/products/product_card.dart`: `MemberPriceTag`); kurallar bölüm 14 |
| D2-2. Fiyat birimi notu ("kg fiyatı") | **Bitti** (`PriceWithUnit`); kurallar bölüm 14 |
| D2-3. Uzun katalogda sayfaya atlama | **Bitti** (`lib/features/brochure/page_picker_screen.dart`); kurallar bölüm 8 |
| D3-1. Ana ekranda "Ürün ara" girişi | **Bitti** (`lib/features/search/search_entry_button.dart`); kurallar bölüm 7 ve 15 |
| D3-2. Arama ekranı (yazmadan önce, bekleme, sonuç, bulunamadı, internet yok) | **Bitti** (`lib/features/search/`); kurallar bölüm 15 |
| D3-3. Sonuçtan broşüre: sayfa ya da "Aradığınız ürün" en üstte | **Bitti** (`navigation.dart`: `openSearchHit`; `ProductList.highlight`); kurallar bölüm 15 |
| D3-4. Yeni marketlerin ad kartı renkleri | **Bitti** (`lib/design/chain_logos.dart`: `chainPlateColors`); kurallar bölüm 6 |
| D4-1. Ana ekranda bildirim denetimi (kapalı / açık / telefonda kapalı; kullanılamıyorsa hiçbir şey) | **Bitti** (`lib/features/notifications/notification_control.dart`); kurallar bölüm 16 |
| D4-2. İlk yıldızdan sonra bir kez teklif penceresi, telefonun izninden önce tek cümle | **Bitti** (`notification_offer.dart`, `notification_offer_store.dart`); kurallar bölüm 16 |
| D4-3. Bildirime dokununca broşür ya da market | **Bitti** (`notification_tap_handler.dart`, `app.dart`); kurallar bölüm 16 |
| D4-4. Telefonda kapalıyken "Telefon ayarlarını aç" düğmesi | **Bitti** (`openSystemSettings()`; açılamazsa yazılı adımlar kendiliğinden açılır); kurallar bölüm 16 |
| 3B.3-1. "Broşürden okundu" satırı ve "Broşürde gör, sayfa 3" düğmesi | **Bitti** (`product_card.dart`: `OcrSourceTag`); kurallar bölüm 17 |
| 3B.3-2. Şok / Hakmar broşüründe "Broşür / Ürünler" sekmeleri, listenin başında tek açıklama | **Bitti** (`brochure_screen.dart`: `hasProductList`; `product_list.dart`); kurallar bölüm 17 |
| 3B.3-3. Aramada etiket, sayfaya açılış, artık doğru olmayan metinlerin yenilenmesi | **Bitti** (`search_screen.dart`, `search_result_card.dart`, `app_tr.arb`); kurallar bölüm 15 ve 17 |
| Testler (D2 sonu) | `flutter test`: 226 geçiyor (114 veri + 112 arayüz; 2 araç testi bilerek atlanır). D2 testleri `test/ui/prices_and_pages_test.dart` |
| Testler (D4 sonu) | `flutter test`: 413 geçiyor, 11 bilerek atlanır (2 simge + 9 ekran görüntüsü aracı); `flutter analyze` temiz. D4 testleri `test/ui/notifications_test.dart` (78) |
| Testler (3B.3 sonu) | `flutter test`: 508 geçiyor, 11 bilerek atlanır; `flutter analyze` temiz. 3B.3 testleri `test/ui/ocr_test.dart` (39) |
| Ekran görüntüleri | `design/screenshots/`, hepsi WebP (açık, koyu, büyük yazı, yakınlaştırılmış, uçak modu). D2: `40`–`42` üyelik fiyatlı ürün listesi (açık, koyu, büyük yazı), `43` uzun katalogda sayfa göstergesi düğmesi, `44`–`46` "Sayfa seç" ekranı (açık, koyu, büyük yazı); D4: `61`–`69` bildirim (aşağıdaki not) |

Emülatörde (Medium_Phone) uçtan uca denenen akış: aç → market → broşür → + ile ve çift dokunmayla
yakınlaştır → büyütülmüşken kaydır (sayfa değişmedi) → okla sayfa değiştir → geri → favori işaretle →
uygulamayı kapat aç (favori üstte) → uçak modunda daha önce açılan broşür ve ürün listesi açıldı.
D2 için örnek veriyle denenen akış: Migros ürün listesi (üç üyelik fiyatlı kart; açık, koyu, yazı
ölçeği 2,0) ve Watsons (46 sayfa) → "1 / 46" düğmesi → "Sayfa seç" → 23 → görüntüleyici 23. sayfada
açıldı. Üyelik fiyatı canlı veriyle emülatörde denenmedi.
İki parmakla yakınlaştırma emülatörde `adb` ile üretilemediği için yalnızca widget testiyle doğrulandı
(`test/ui/viewer_test.dart`, "two fingers zoom the page and never turn it"); gerçek cihazda bir kez
elle denenmesi iyi olur. iOS tarafı (ad, simge, açılış zemini) Mac olmadığı için derlenip denenmedi.

Derleme notu: bu makinede `flutter build apk --debug` yalnızca şu ortam değişkeniyle çalışıyor
(boşluksuz, kısa bir klasör): `JAVA_TOOL_OPTIONS=-Djdk.net.unixdomain.tmpdir=C:\Users\Public\uds`.

D4 (bildirim) ekran görüntüleri `61`–`69` emülatörden değil **widget testinden** çekildi
(`test/tools/notification_screenshots_test.dart`, `--dart-define=SCREENSHOTS_DIR=…`; uygulamaya
girmez): Firebase yapılandırması olmayan yapıda durum `unavailable`dır ve hiçbir şey görünmez, durumlar
testlerdeki sahte sağlayıcıyla üretildi. Gerçek yazı tipleri, logolar ve simgeler, Medium_Phone ölçüsü;
sistem durum çubuğu yok. `61` kapalı, `62` ilk yıldızdan sonra teklif, `63` açık, `64` telefonda kapalı
("Telefon ayarlarını aç" + "Elle nasıl açılır?"), `65`–`66` koyu teklif / açık, `67`–`68` yazı ölçeği
2,0 teklif / açık, `69` 320 dp + 2,0 telefonda kapalı (yazılı adımlar açık). Telefonun gerçek izin penceresi ve gerçek bildirim emülatörde **denenmedi**.

D3 testleri `test/ui/search_test.dart` (durumlar, sıra, üyelik fiyatı, ekran okuyucu etiketi, sonuçtan
broşüre geçiş; yazı ölçeği 1,0 / 1,3 / 2,0 × açık / koyu × 411 / 320 dp taşma denemeleri, klavye açıkken
dahil) ve `test/ui/tokens_test.dart` (ad kartı renkleri). Güncel test sayısı ve D3 ekran görüntüleri
bölüm 15'in sonunda.

3B.3 (broşürden okunan fiyatlar) ekran görüntüleri `70`–`75` emülatörden (Medium_Phone, örnek veri,
Şok "11–17 Kasım" broşürü): `70` ürün listesi, `71` "lastik" araması (aynı adlı iki ürün, "2 cm" / "3 cm"),
`72` koyu "omo" araması, `73` koyu ürün listesi, `74` yazı ölçeği 2,0 liste başı, `75` yazı ölçeği 2,0 kart.
Emülatörde denenen akış: ana ekran → Şok → 11–17 Kasım → "Ürünler" → "Broşürde gör, sayfa 2" → görüntüleyici
2 / 4'te; "Ürün ara" → "lastik" → sonuca dokun → Şok 2 / 4'te. Örnek veride Şok sayfa görselleri gömülü
olmadığı için sayfanın kendisi "Bu sayfa açılamadı" gösterir (bölüm 13); doğru sayfaya gidildiği göstergeden
ve ekran okuyucu ağacından doğrulandı. Canlı OCR dosyasıyla henüz denenmedi.

Bilinen açık noktalar bölüm 13'te.

## 1. Kim için, hangi ilkeyle

Asıl kullanıcı yaşlı bir teyze: yakını iyi görmüyor, küçük hedeflere isabet edemiyor, gizli
hareketleri (kaydırarak geri, uzun basma, menü simgesi) bilmiyor, kaybolmaktan korkuyor. Yapmak
istediği tek şey: marketi seçmek, bu haftanın broşürünü açmak, yazıyı okuyacak kadar büyütmek.

1. **Her ekranda tek iş.** Ana ekran: market seç. Market ekranı: broşür seç. Görüntüleyici: oku.
2. **Görünür düğme her zaman vardır.** İki parmak, çift dokunma, kaydırma çalışır ama hiçbir iş
   yalnızca bir harekete bağlı değildir: yakınlaştırmanın + / − düğmesi, sayfa çevirmenin oku,
   geri dönmenin "Geri" düğmesi vardır.
3. **Denetimler kaybolmaz.** Görüntüleyicide çubuklar dokununca gizlenmez; içeriğin üstüne düğme
   bindirilmez (broşür sayfası kutsaldır, fiyat çoğu zaman köşededir).
4. **Geri her zaman bir önceki ekrana döner.** Kullanıcının görmediği bir ara ekran araya girmez.
5. **Arayüz susar, logo ve broşür konuşur.** Marketlerin renkleri bütün renk çemberini kaplar;
   arayüz bu yüzden kâğıt ve mürekkep tonlarında kalır, tek bir eylem rengi kullanır.
6. **Sözcükler gündelik Türkçe.** "Bu hafta", "Geri", "Tekrar dene". Teknik sözcük, kısaltma,
   İngilizce yok. Hata iletisi önce ne olduğunu, sonra ne yapılacağını söyler; suçlamaz.

## 2. Renk

Dil: **kâğıt ve mürekkep**. Sıcak krem zemin (kâğıt), sıcak siyah yazı (mürekkep), tek eylem rengi
**çarşı yeşili** (esnaf tentesi yeşili). Belirteçler `lib/design/tokens.dart` içinde `AppColors`
(`ThemeExtension`); ekranda `context.colors.<rol>` ile okunur.

| Rol | Açık | Koyu | Nerede |
|---|---|---|---|
| `paper` | `#F6F1E7` | `#161411` | Ekran zemini |
| `surface` | `#FFFDF9` | `#24211C` | Kartlar, çubuklar |
| `surfaceSunken` | `#E9E1D1` | `#0D0C0A` | Görüntüleyicide sayfanın yattığı "masa", yer tutucular |
| `ink` | `#1D1A16` | `#F4EEE3` | Ana yazı, simgeler |
| `inkSoft` | `#564E44` | `#C6BCAC` | İkincil yazı (zeminde en az 7:1) |
| `line` / `lineStrong` | `#DDD4C2` / `#8A7F6D` | `#3B362E` / `#8E8473` | İnce ayraç / denetim çerçevesi (en az 3:1) |
| `primary` / `onPrimary` | `#1F5A45` / beyaz | `#8AD4B0` / `#0B2A1F` | Ana düğmeler, seçili sekme |
| `primarySoft` / `onPrimarySoft` | `#DCE9DF` / `#143D2F` | `#213F33` / `#CFEBDD` | Sakin düğmeler, vurgu zemini |
| `star` / `starOutline` | `#F2B01E` / `#6B4A00` | `#FFC83D` | Favori yıldızı (dolu) ve çerçevesi |
| `fresh` / `onFresh` | `#B5281C` / beyaz | `#FF9D8C` / `#3B0A05` | "Yeni" rozeti, indirim etiketi |
| `scrim` | mürekkep %60 | siyah %70 | Pencerenin (bildirim teklifi) arkasındaki karartma |
| `notice` / `onNotice` / `noticeLine` | `#FBEBC2` / `#3D2E00` / `#DDBF6A` | `#3A2F12` / `#FBE7B5` / `#6B5720` | Sakin bilgi şeridi (internet yok, veri eski, güncelleme) |
| `logoPlate` | beyaz | `#FAF8F4` | Market logosunun arkasındaki plaka |

Kurallar:
- **Kontrast:** gövde yazısı zeminde en az 7:1, düğme yazısı en az 4,5:1, denetim çerçevesi en az
  3:1. `test/design/tokens_test.dart` bunu iki tema için de ölçer; yeni renk eklenince test de eklenir.
- **Bilgi yalnızca renkle verilmez.** "Yeni" bir sözcüktür, favori dolu / boş yıldız biçimidir,
  uyarı şeridinde simge vardır.
- **Kırmızı hata rengi değildir.** `fresh` yalnızca "Yeni" ve indirim için kullanılır. İnternet
  yokluğu bir felaket değil, bir durumdur: `notice` şeridiyle, sakin bir dille söylenir.
- **Logo plakası iki temada da beyazdır.** Logolar beyaz zemin için çizilmiştir (BİM logosunun
  harfleri saydamdır); koyu temada plakayı karartmak markayı bozar.
- **Koyu tema** saf siyah değil sıcak koyudur; kartlar gölgeyle değil bir ton açık yüzey ve ince
  çizgiyle ayrılır.

Yap: `color: context.colors.inkSoft`. Yapma: `color: Colors.grey`, `Color(0xFF...)`,
`Theme.of(context).colorScheme.primary` (şema yalnızca hazır Material bileşenleri içindir).

## 3. Yazı

İki aile, ikisi de SIL OFL lisanslı ve uygulamaya gömülü (`assets/fonts/`, lisans metinleri yanında);
çalışırken internetten hiçbir şey inmez.

- **Lexend** (400 / 500 / 600 / 700): okunan ve basılan her şey. Okuma kolaylığı araştırmasına
  dayanan geniş, açık harfler ve ferah aralık; yaşlı gözde harflerin birbirine yapışmasını azaltır.
  Türkçe seti eksiksiz (ğ, ş, ı, İ, ç, ö, ü) ve **₺ işareti var**.
- **Fraunces** (600): yalnızca büyük başlıklar (uygulama adı, ekran başlığı, bölüm başlığı).
  Yumuşak, basılı broşür / kitap sesi verir; logo fikriyle (kitap) aynı dünyadan.

Neden Atkinson Hyperlegible değil: az görenler için tasarlanmış olması onu ilk aday yaptı, ancak
dosyaları incelendiğinde **₺ işaretinin bulunmadığı** görüldü (Atkinson Hyperlegible Next ve Mono'da
U+20BA yok; eski sürümde İ de yok). Fiyat bu uygulamanın en önemli metni olduğu için elendi.

Ölçek (`lib/design/typography.dart`, `AppType`). **Hiçbir yazı 18 sp'den küçük değildir.**

| Stil | Aile / ağırlık | Boyut | Kullanım |
|---|---|---|---|
| `wordmark` | Fraunces 600 | 34 | "Çarşı Pazar" |
| `headline` | Fraunces 600 | 28 | Ekran başlığı, market adı |
| `section` | Fraunces 600 | 24 | "Bu hafta", "Gelecek hafta" |
| `title` | Lexend 600 | 21 | Kart başlığı, tarih, üst çubuk |
| `body` | Lexend 400 | 18 | Akan metin |
| `bodyStrong` | Lexend 600 | 18 | Kart alt yazısı, vurgulu metin |
| `label` | Lexend 600 | 20 | Düğme yazısı |
| `badge` | Lexend 700 | 18 | "Yeni", "%20 indirim" |
| `chainName` | Lexend 700 | 38 | Logosu olmayan marketin ad kartı |
| `price` / `priceOld` | Lexend 700 / 500 | 28 / 18 | Raf fiyatı / üstü çizili eski fiyat (sabit genişlikli rakam) |
| `memberPrice` | Lexend 700 | 24 | Üyelik fiyatı, yalnızca etiketli kutusunun içinde (bölüm 14) |
| `pageIndicator` | Lexend 700 | 24 | "3 / 8" |

Sistem yazı büyütmesi **%200'e kadar** aynen uygulanır (`maxTextScale`). Bu yüzden:
- Metin taşıyan hiçbir kutunun yüksekliği sabit değildir; metin sarar, kutu uzar.
- Yan yana duran metin + düğme düzenleri dar kalınca alt alta geçer (`Wrap` ya da ölçüye göre).
- Yalnızca iki yerde yazı kutuya sığdırılır (`FittedBox`, küçülür ama asla kesilmez): ad kartındaki
  market adı (logo yerine geçen bir grafiktir) ve görüntüleyicideki "3 / 8".
- Ok karakteri (← →) yazıya konmaz (yazı tiplerinde yok); yön için simge kullanılır.

## 4. Ölçü, köşe, gölge, hareket

- **Dokunma hedefi** en az `AppSize.touch` = 56 dp; ana düğmeler ve görüntüleyici okları
  `AppSize.touchLarge` = 64 dp. İki hedef arasında en az `AppSpace.xs` = 8 dp boşluk.
- **Boşluk ölçeği** `AppSpace`: 4, 8, 12, 16, 20, 24, 32, 48. Ekran kenarı 16.
- **Köşe** `AppRadius`: 10 (plaka, görsel), 14 (düğme, şerit), 20 (kart), hap (rozet).
- **Gölge** `AppShadows.card`: yalnızca açık temada, yumuşak ve sıcak; koyu temada çizgi.
- **Hareket** `AppMotion`: 160 / 240 ms, `easeOutCubic`. Ekran geçişi kısa bir belirme + hafif
  yükselme (`CalmPageTransitionsBuilder`); yana kayma yok, çünkü "kaydırarak geri" hareketini
  çağrıştırır. Sistemde "hareketi azalt" açıksa bütün hareketler kapanır
  (`context.reduceMotion`, `context.motion(...)`).

Yap: `padding: EdgeInsets.all(AppSpace.md)`. Yapma: `EdgeInsets.all(16)`, `SizedBox(height: 10)`.

## 5. Logo ve açılış

**Fikir:** açık bir broşür, üstünde çizgili bir çarşı tentesi. Broşür tezgâhın kendisidir:
"içinden çarşının çıktığı kitap". Kitap sahibinin isteği, tente adı ("Çarşı Pazar") bağlar.

- Çizim kodda (`lib/design/widgets/logo_mark.dart`, `LogoPainter`, 100 × 100 ızgara); aynı çizim
  açılışta, ana ekran başlığında ve uygulama simgesinde kullanılır. Renkleri logoya aittir
  (`LogoPalette`: kâğıt üstü, koyu zemin, yeşil simge zemini), arayüz paletinden ayrı tutulur.
- **Açılış** (yaklaşık 1,9 sn): tente açılır, broşürün sayfaları sağdan sola art arda hızla
  çevrilir (her sayfanın arkası başka bir renk: "marketlerin broşürleri geçiyor"), sonra uygulama
  adı belirir. Veri bu sırada arka planda yüklenir; açılış veriyi beklemez, veri açılışı bekletmez
  (ana ekran açılışın altında ilk kareden kurulur, açılış üstünden solarak kalkar: `SplashGate`).
- Hareket, ilk kare gerçekten ekrana gelince başlar (`waitUntilFirstFrameRasterized`); yoksa soğuk
  açılışta sistem açılış ekranının arkasında, kimse görmeden oynar.
- Android'in kendi açılış ekranı kâğıt renginde zemin üstünde uygulama simgesini gösterir
  (`res/values*/colors.xml`, `styles.xml`); böylece sistem ekranından bizim açılışa geçişte renk
  sıçramaz.
- "Hareketi azalt" açıksa: sayfa çevrilmez, durağan logo ve ad kısa süre görünür.
- Uygulama simgesi logodan üretilir (yeşil zemin, krem kitap, safran tente); Android uyarlanabilir
  simge ve iOS simge seti dahil. Logo çizimi değişirse yeniden üret:
  `flutter test test/tools/generate_icons_test.dart --dart-define=GENERATE_ICONS=true`.

## 6. Market logoları

- Dosyalar `assets/logos/<chain_id>.png`; kayıt `lib/design/chain_logos.dart`. Her logo yalnızca o
  marketi tanıtmak için, bozulmadan (yeniden renklendirme, kırpma, eğme yok) beyaz plakada gösterilir.
  Yalnızca saydam kenar boşlukları kırpılmış, büyük dosyalar küçültülmüştür.
- Kaynak: her zincirin kendi resmi sitesi (13 Kasım 2026): BİM `bim.com.tr`, Şok
  `kurumsal.sokmarket.com.tr`, Migros `migroskop.migros.com.tr`, CarrefourSA `carrefoursa.com`
  (görsel sunucusu), Gratis `gratis.com`.
- Migros logosu beyazdır; kendi turuncu zemini üstünde gösterilir (kayıtta `onBrandColor`).
- **A101 ve Watsons'ın logosu yok:** A101 sitesi 403 döndü, Watsons ana sitesi engelli; engel
  dolanılmadı. Bu ikisi **ad kartı** ile gösterilir.
- **Ad kartı:** plaka markanın rengiyle dolar (`chain.brandColor`), ad büyük ve kalın yazılır;
  yazı rengi beyaz ya da siyahtan hangisi daha okunaklıysa o seçilir (`AppColors.onBrand`), böylece
  hangi renk gelirse gelsin en az 4,5:1 kontrast kalır (testle doğrulanır). Renk de yoksa `primarySoft` zemin.
  Yeni bir zincir geldiğinde hiçbir kod değişmeden ad kartıyla çalışır. **Uydurma logo çizilmez.**
- **Katalog renk vermiyorsa** (`brand_color` yok) ad kartının rengi `chain_logos.dart` içindeki
  `chainPlateColors` kaydından gelir; katalogdaki renk varsa her zaman o kazanır. Şimdilik beş market:
  Hakmar `#D62B1F` (sıcak kırmızı), bonVeno `#B5175E` (ahududu), Metro `#003B7E` (lacivert), Rossmann
  `#B00030` (koyu kırmızı), Tarım Kredi Market `#00843D` (yeşil). Renkler marketin kendi broşür ve
  tabelasındaki baskın renge **yakın** seçilmiştir, resmî kurumsal renk kodu oldukları iddia edilmez;
  yalnızca düz zemin rengidir, logo ya da logo benzeri bir çizim değildir. İki kırmızı (Hakmar, Rossmann)
  bilerek farklı sıcaklıktadır; yine de marketi ayıran şey renk değil, büyük yazılmış **addır**.
  Her renk için yazı rengi `onBrand` ile seçilir ve en az 4,5:1 kontrast testle doğrulanır.
  Kazıyıcı ileride bu marketlere `brand_color` yazarsa kayıttaki satır silinebilir.
- Yeni logo eklemek: dosyayı `assets/logos/` altına koy, `chain_logos.dart` içine bir satır ekle.

## 7. Ekranlar ve akış

```
Açılış → Ana ekran ─┬─ (web görünümü zinciri) ───────────────→ Web görünümü
                    ├─ (tek broşürü olan market) ────────────→ Broşür
                    ├─ Market ekranı → Broşür (sayfalar ⇄ ürün listesi)
                    └─ "Ürün ara" → Arama → Broşür (ürünün sayfası ya da listesi)
Bildirime dokunma ──────→ Broşür (katalogda varsa) ya da market (kartı gibi)
```

**En az dokunuş kuralı:** bir marketin gösterilecek **tek** broşürü varsa (bu hafta + gelecek +
geçmiş toplamı 1) market ekranı atlanır, karta basınca broşür doğrudan açılır; "Geri" ana ekrana
döner. Birden fazla broşür varsa market ekranı açılır. Gerekçe: seçecek bir şey yokken seçim ekranı
göstermek boş bir adımdır; ama araya kullanıcının görmediği bir ekran sokup "Geri"yi oraya
düşürmek (ilke 4) daha kötüdür, o yüzden yalnızca gerçekten tek seçenek varken atlanır.

### Ana ekran
- Üstte logo + "Çarşı Pazar", altında "Ürün ara" düğmesi, onun altında tek soru: "Hangi markete
  bakalım?". Menü, sekme, köşede büyüteç simgesi yok.
- 2 sütun market kartı. Kart: üstte kenardan kenara logo plakası (ya da ad kartı), altında iki
  satır durum (kalın "Bu hafta" / "Gelecek hafta" / "Geçmiş" + "2 broşür"; ya da "Marketin sitesi",
  "Broşür yok") ve sağ altta favori yıldızı (56 dp hedef). Kartın tamamı tek düğmedir, yalnızca
  yıldız ayrı hedeftir.
- Yıldız ve "Yeni" rozeti **logonun üstüne bindirilmez**: yıldız alt şeritte durur, "Yeni" kartın sol
  üst köşesinden dışarı taşan bir etiket gibidir (logo plakasının iç boşluğuna denk gelir).
- Market verisi bayatsa durum satırında küçük bir "bulut kapalı" simgesi çıkar (ekran okuyucuda
  "Son bilgiler alınamadı").
- Favoriler "Sık baktıklarım" başlığıyla üstte, kalanlar "Diğer marketler" altında. Favori yokken
  başlık yoktur; ızgaranın altında yıldızı öğreten tek cümlelik ipucu durur.
- Yıldıza basınca kart yer değiştirir ve ne olduğu alttan çıkan iletiyle söylenir
  ("Şok en üste alındı."), çünkü kart parmağın altından kaybolur.
- Sistem yazı ölçeği 1,3'ün üstündeyse ızgara tek sütuna düşer (yoksa "broşürler" gibi sözcükler
  kartın içinde ortadan bölünür). Aynı eşik üst çubukların alt alta geçmesini de yönetir
  (`context.useStackedBars`).
- Aşağı çekip yenileme çalışır ama tek yol değildir: listenin sonunda "Broşürleri yenile" düğmesi var.
- **"Ürün ara" girişi** (`SearchEntryButton`): uygulama adının hemen altında, sorunun **üstünde**, tam
  genişlikte, en az 64 dp yüksekliğinde tek düğme. Solda yeşil kare içinde büyüteç, yanında kalın
  "Ürün ara" ve altında ne işe yaradığını söyleyen "Hangi markette kaç lira?". Gerekçeler:
  - Sorunun üstünde durur, çünkü "Hangi markete bakalım?" sorusunun cevabı hemen altındaki market
    kartlarıdır; araya düğme girerse soru ile cevabı kopar.
  - Dolu yeşil (`primary`) değil, "krem zemin + koyu çerçeve" düğmesidir: ana ekranın asıl işi market
    seçmektir, arama ikinci yoldur. Yeşil yalnızca büyüteç karesindedir; düğmeyi kartlardan ayırır.
  - Yalnızca simge değil **sözcük**: köşedeki büyüteç bu kullanıcı için görünmezdir.
  - Katalog daha yüklenmemişken (ilk açılış, internet yok) düğme gösterilmez; basılınca yalnızca bekleme
    ya da hata gösterecek bir düğme ilk ekranı kalabalıklaştırır.

### Market ekranı
- Üst çubuk: "Geri", market logosu / adı, favori yıldızı.
- Bölümler: "Bu hafta", "Gelecek hafta", "Geçmiş broşürler". Boş bölüm gösterilmez.
- Broşür kartı tam genişlikte: solda kapak, sağda büyük tarih ("13–19 Kasım"), başlık (tarihi
  yineliyorsa tarih kısmı atılır: "13 Kasım Cuma Aktüel Ürünler" → "Aktüel Ürünler"), sayfa / ürün
  sayısı ve düğme biçiminde bir "Aç ›" işareti. Kartın tamamı düğmedir; "Aç" yalnızca "buraya basılır"
  demek içindir.
- "Bu hafta" altında en çok 2 broşür varsa kapak büyük ve "Aç" birincil renkte olur; daha çoksa
  (BİM'de 11 olabiliyor) liste uzamasın diye olağan boyuta döner.
- "Bu hafta" içinde en yeni başlayan broşür en üsttedir (bkz. bölüm 13).
- Market verisi bayatsa en üstte sakin şerit: son iyi verinin tarihiyle.

### Broşür (sayfalar)
Bkz. bölüm 8.

### Ürün listesi
- Tek sütun büyük kartlar: ad (kalın), marka, fiyatlar; ürün fotoğrafı varsa solda. Fiyatların
  görsel dili bölüm 14'te (raf fiyatı, eski fiyat, üyelik fiyatı, birim notu).
- Broşürde sayfa da varsa (`kind: both`, ya da sayfalardan okunmuş fiyatlar: `hasProductList`) üstte
  iki büyük sekme: "Broşür" | "Ürünler". Sekme her zaman görünür; üründe sayfa numarası varsa "Sayfada
  göster" düğmesi (broşürden okunan fiyatta "Broşürde gör, sayfa 3") o sayfayı açar (bölüm 17).
- Aramadan gelindiyse (`ProductList.highlight`) liste "Aradığınız ürün" başlığı ve yeşil çerçeveli
  kartla başlar, altında "Bu broşürdeki bütün ürünler" başlığıyla listenin tamamı sürer (bölüm 15).

### Web görünümü (A101, CarrefourSA, Gratis)
- Üst çubukta "Geri" her zaman uygulamaya döner. Site içinde gezinme için altta "Sitede geri"
  (yalnızca gidilecek sayfa varken) ve "Tarayıcıda aç". Telefonun kendi geri tuşu önce site içinde
  geri gider.
- Sitenin kendi çerez / uygulama pencerelerine dokunulmaz; kullanıcının kararıdır.
- Web dışı bağlantılar (uygulama mağazası, `intent:`) açılmaz; kullanıcı uygulamadan dışarı düşmez.
- Yüklenirken çubuğun altında ilerleme çizgisi. Sayfa açılamazsa sade açıklama + "Tekrar dene" +
  "Tarayıcıda aç".

## 8. Broşür görüntüleyici (işin kalbi)

**Karar: `InteractiveViewer` üstüne kendi bileşenimiz (`photo_view` değil).** Gerekçe: `photo_view`
yakınlaştırılmış sayfa kenara dayanınca kaydırmayı sayfa çevirmeye devreder; teyze yazıyı okumak
için parmağını kaydırırken sayfa aniden değişir ve kaybolur. Bizde kural kesin ve tek cümle:

> **Sayfa büyütülmüşken kaydırmak yalnızca sayfanın içinde gezdirir; sayfa asla kendiliğinden
> değişmez. Sayfa yalnızca oklarla ya da sayfa büyütülmemişken kaydırarak değişir.**

Uygulama kuralları:
- Sayfa çevirici (`PageView`) kaydırması, ölçek 1'in üstündeyken **ve** ekranda iki parmak varken
  kapatılır; böylece iki parmakla açma hareketi sayfa kaydırmaya karışmaz.
- Ölçek 1'deyken tek parmakla yatay kaydırma sayfa çevirir; sayfa içi kaydırma kapalıdır.
- **Çift dokunma:** dokunulan noktaya 2,5× yaklaşır; yeniden çift dokunma sayfayı sığdırır.
- **+ / −:** her basış 1,6×, ekranın ortasına doğru, hareketli. Sınırda düğme soluklaşır ama yerinde
  kalır. Ok ile sayfa değişince büyütme sıfırlanır (yeni sayfa bütün görünür).
- **En büyük ölçek** görselin çözünürlüğüne göre: `(görsel px / ekran px) × 2`, en az 4×, en çok 8×.
  Düşük çözünürlüklü BİM afişi (940 px) de 4× büyür: yumuşak ama büyük harf, keskin ama minik
  harften daha okunaklıdır. Yüksek çözünürlüklü sayfa (Watsons 1960 × 2940, Metro 1800 × 3200)
  ayrıntısı bitene kadar büyür.
- Sayfa sığdırılmışken küçültme pürüzsüz olsun diye `FilterQuality.medium` (mipmap); çok büyük
  görseller en uzun kenarı 3200 px olacak biçimde çözülür (bellek).
- Sayfa, ekrandan küçük kaldığı eksende ortalanır; büyük olduğu eksende kenarı ekran kenarını
  geçemez (boş alana kaydırılmaz).
- Katalog sayfa ölçüsünü veriyorsa (`aspectRatio`) görsel gelmeden yeri ayrılır; sayfa "masa"
  (`surfaceSunken`) üstünde hafif gölgeli bir kâğıt gibi durur.
- **Alt çubuk** (her zaman görünür): `‹` `3 / 8` `›` ve ayrı bir grupta `−` `+`. Oklar birincil
  renkte ve 64 dp; yakınlaştırma düğmeleri sakin renkte ve 56 dp. İlk sayfada `‹`, son sayfada `›`
  soluklaşır.
- **İnternetsiz okuma:** sayfa görselleri diske önbelleklenir (`AppCachePolicy`: 45 gün, en az 30
  gün koşulunu sağlar). Broşür açılınca 16 sayfaya kadar olan broşürlerin tamamı arka planda
  kaydedilir; daha uzun kataloglar (Watsons 46 sayfa, sayfa başı ~1 MB) okundukça ve 3 sayfa
  ileriye doğru kaydedilir (mobil veriyi bir dokunuşta 40 MB harcamamak için).
- Görsel yüklenemezse sayfanın yerinde sade ileti + büyük "Tekrar dene"; oklar çalışmaya devam eder
  (sonraki sayfa önbellekte olabilir).
- **Üst çubuk** bu ekranda yazı ne kadar büyük olursa olsun tek satırdır (`keepOnOneRow`): başlık
  "Geri"nin yanında kalır, sığmazsa küçülür. Gerekçe: burada her dp sayfanındır; başlık yalnızca
  kullanıcının az önce seçtiği şeyi doğrular.
- Denetimler dokununca gizlenmez; "tam ekran" kipi yoktur (ilke 3).

### Sayfaya atlama (uzun kataloglar)

Watsons kataloğu 46 sayfa; ortadaki bir sayfaya gitmek için oka 20 kez basmak gerekmemeli.

- **9 sayfa ve üstünde** (`AppZoom.pagePickerMinPages`) alt çubuktaki "3 / 46" göstergesi bir düğmeye
  dönüşür: aynı yerde, aynı yazı, ama "Geri" ile aynı çerçeveli düğme biçiminde ve 56 dp. 8 sayfa ve
  altında gösterge düz yazı olarak kalır; kısa broşürde oklar zaten daha hızlıdır ve çubuk
  kalabalıklaşmaz.
- Düğme **"Sayfa seç"** ekranını açar: her sayfa için büyük, numaralı bir düğme (telefonda 5 sütun,
  46 sayfa tek ekrana sığar; çok büyük yazıda 3 sütun). Bulunulan sayfa dolu (birincil renk) ve ekran
  okuyucuda "şu an buradasınız" diye okunur; ekran o sayfa görünür biçimde açılır.
- **Tam ekran, alt sayfa (bottom sheet) değil.** Alt sayfa sürükleyerek kapatılır; bu gizli bir
  harekettir. "Sayfa seç" her ekrandaki "Geri" ile kapanır ve sayfa değişmeden döner.
- **Yalnızca numara, küçük görsel yok.** Publitas'ta ve kendi WebP'lerimizde ayrı küçük görsel yok;
  küçük resim göstermek her sayfanın tamamını indirmek demek (Watsons'ta 46 × ~1,2 MB). Mobil veriyi
  bir dokunuşta harcamamak, "şampuan sayfası"nı resminden bulmaktan önce gelir. Kazıyıcı ileride
  küçük görsel üretirse bu ekran onları numaranın üstünde gösterebilir.
- Numaraya basınca o sayfaya **doğrudan** gidilir (aradaki sayfalardan kayarak geçilmez) ve büyütme
  sıfırlanır.
- Göstergenin yanına simge konmaz: dar çubukta rakamları küçültüyordu (denendi). Bu uygulamada
  "krem zemin + koyu çerçeve" her yerde "basılır" demektir.

## 9. Durumlar

| Durum | Görünüş |
|---|---|
| İlk yükleme | Açılış bitince veri hâlâ gelmediyse kart iskeletleri + "Broşürler getiriliyor…" |
| İnternet yok, kayıt yok | Tam ekran: çizim, "İnternete bağlanılamadı", ne yapılacağı, büyük "Tekrar dene" |
| İnternet yok, kayıt var (`isStale`) | Ana ekranın üstünde sakin şerit: "İnternet yok. Daha önce açtığınız broşürleri okuyabilirsiniz." |
| Market verisi bayat (`chain.isStale`) | Market ekranında şerit: son alınma tarihiyle; kartta küçük simge |
| Görsel yüklenemedi | Kapakta kâğıt yer tutucu; sayfada ileti + "Tekrar dene" |
| Boş market | "Şu an broşür yok" + "Marketin sitesine bak" |
| Güncelleme gerekli | Ana ekranın üstünde şerit: "Uygulamanın yeni sürümü gerekiyor…" |
| Arama: yazmadan önce | "Ne arıyorsunuz?", örnek sözcük düğmeleri, arama yapılan marketler, fiyat notu (bölüm 15) |
| Arama: hazırlanıyor | Halka + "Broşürlerdeki ürünler hazırlanıyor…"; yazı alanı bu sırada da kullanılır |
| Arama: bulunamadı | "“kivi” bulunamadı", ne denenebileceği, hangi marketlere bakıldığı, "Başka ürün ara" |
| Arama: internet yok, kayıt var | Sakin şerit: "Yalnızca daha önce açtığınız broşürlerde aranıyor." |
| Arama: yapılamıyor | Tam alan: "Arama şu an yapılamıyor" + "Tekrar dene" |
| Bildirim: kullanılamıyor / bilinmiyor | Hiçbir şey (bölüm 16) |
| Bildirim: telefonda kapalı | Krem panel, büyük "Telefon ayarlarını aç"; altında "Elle nasıl açılır?" ile üç adım; sarı uyarı değil (bölüm 16) |

Dil kuralı: önce ne olduğu, sonra ne yapılabileceği. "Hata", "bağlantı zaman aşımı", "sunucu" gibi
sözcükler kullanılmaz.

## 10. Kod düzeni ve kurallar

```
lib/design/            belirteçler, tema, yazı, logo kaydı
lib/design/widgets/    ekranlardan bağımsız bileşenler (düğme, şerit, durum görünümü, görsel…)
lib/features/<ekran>/  ekranlar; yalnızca Riverpod sağlayıcılarını ve design/ bileşenlerini kullanır
lib/l10n/app_tr.arb    bütün metinler
```

- Ekran kodunda `Color(0x…)`, çıplak ölçü sayısı ve sabit metin **olmaz**.
- Ekranlar `http`, dosya sistemi, `rootBundle` çağırmaz; veri yalnızca `lib/data/data.dart`
  sağlayıcılarından gelir. Görsel adresleri her zaman `catalogRepositoryProvider.resolve` ile çözülür.
- Her etkileşimli öğenin ekran okuyucu etiketi vardır (`Semantics` / `tooltip`), süs olanlar
  `ExcludeSemantics` ile gizlenir.
- Yeni bileşen önce `lib/design/widgets/` altına yazılır, widget testi eklenir, bu belgeye işlenir.

## 11. Bileşen dökümü

`lib/design/widgets/` altındakiler ekranlardan bağımsızdır; yeni ekran önce bunlardan kurulur.

| Bileşen | Dosya | Ne zaman |
|---|---|---|
| `AppScaffold`, `AppTopBar`, `BackButtonPill`, `ContentWidth` | `app_scaffold.dart` | Her ekranın çerçevesi; "Geri" her zaman simge + sözcük, 56 dp. `keepOnOneRow` yalnızca içerik yüksekliği kıymetli ekranlarda (görüntüleyici, web) |
| `AppButton` (primary / tonal / outline), `AppIconButton`, `FavoriteStar` | `app_buttons.dart` | Bütün düğmeler. Ekranda en fazla bir `primary`. Basılamayan düğme soluklaşır, yerinden kalkmaz |
| `NoticeStrip` | `feedback.dart` | Sakin durum bildirimi (internet yok, veri eski, güncelleme) |
| `StateView` | `feedback.dart` | Tam alan durum: başlık + tek cümle + büyük düğme |
| `AppCard`, `SectionHeader`, `Pill`, `SkeletonBox`, `showAppMessage` | `feedback.dart` | Kart yüzeyi, bölüm başlığı, "Yeni" / indirim rozeti, yükleme iskeleti, alttan ileti (5 sn) |
| `OpenCue` | `feedback.dart` | Tamamı düğme olan kartın içindeki "Aç ›" işareti (broşür kartı, arama sonucu). Ayrı hedef değildir |
| `InfoNote` | `feedback.dart` | "i" simgeli sakin açıklama satırı: uyarı olmayan ama bilinmesi gereken şey (fiyat nasıl okunur, nerede arandı, fiyatlar broşürden okundu) |
| `ChainMark` | `chain_mark.dart` | Market logosu ya da ad kartı |
| `CatalogImage`, `CoverPlaceholder`, `catalogImageProvider` | `catalog_image.dart` | Katalogdaki her görsel (adres çözme + disk önbelleği burada) |
| `LogoMark`, `LogoPainter`, `LogoPalette` | `logo_mark.dart` | Uygulama logosu |

Ekrana özgü bileşenler: `ChainCard`, `ChainGrid` (ana ekran); `BrochureCard` (market ekranı);
`ZoomablePage`, `PageZoomController`, `ViewerControls`, `ModeTabs`, `PagePickerScreen` (broşür);
`ProductCard`, `ProductFacts`, `PriceWithUnit`, `MemberPriceTag`, `OcrSourceTag`, `ProductList` (ürünler);
`SearchEntryButton`, `SearchScreen`, `SearchField`, `SearchResultCard` (arama); `WebCatalogBar`,
`WebCatalogError` (web); `NotificationControl`, `NotificationOfferDialog`, `NotificationTapHandler`
(bildirim, bölüm 16).

**`ProductFacts`** bir ürünün fotoğrafını, adını, markasını ve fiyatlarını çizen tek yerdir; ürün kartı
da arama sonucu da onu kullanır. Bölüm 14'teki fiyat dili böylece iki ekranda **kendiliğinden** aynıdır;
fiyat gösteren yeni bir ekran da fiyatı kendi çizmez, bunu kullanır.

Test altyapısı: `test/ui/support.dart` (`pumpUi`, `FakeRepository`, `TestImageProvider`,
`uiOverrides`). Arayüz testleri gerçek yazı tipleriyle ölçer; yeni ekranın testi mutlaka yazı ölçeği
2,0 ve 320 dp genişlikte "taşma yok" denemesi içerir.

## 12. Yap / yapma

| Yap | Yapma |
|---|---|
| Rengi `context.colors.<rol>` ile al | `Color(0x…)`, `Colors.grey`, `colorScheme.primary` yazma |
| Ölçüyü `AppSpace` / `AppSize` / `AppRadius` ile ver | `EdgeInsets.all(16)`, `SizedBox(height: 10)` yazma |
| Metni `app_tr.arb`'ye ekle, `l10n.<anahtar>` ile kullan | Kod içine Türkçe metin gömme; iki metni kodda `+` ile birleştirme |
| Yazıyı sarmaya bırak, kutu uzasın | Metin taşıyan kutuya sabit yükseklik, `maxLines: 1` + üç nokta verme |
| Her işin görünür düğmesini koy | Bir işi yalnızca kaydırma, uzun basma ya da çift dokunmaya bağlama |
| Denetimleri sayfanın dışında tut | Broşür sayfasının üstüne düğme, rozet ya da ipucu bindirme |
| Durumu sakin söyle: ne oldu, ne yapılır | "Hata", "sunucu", "zaman aşımı" yazma; kırmızı uyarı kutusu kullanma |
| "Yeni"yi sözcükle, favoriyi biçimle göster | Bilgiyi yalnızca renk farkıyla verme |
| Logoyu beyaz plakada, olduğu gibi göster | Logoyu boyama, kırpma, üstüne rozet koyma; logosu olmayana logo çizme |
| Hareketi `context.motion(...)` ile ver | "Hareketi azalt" ayarını yok sayan animasyon ekleme |
| Görsel adresini `catalogImageProvider` ile çöz | Ekranda `Image.network`, `http`, dosya okuma kullanma |
| Geri'yi bir önceki ekrana döndür | Kullanıcının görmediği ara ekranı yığına sokma |
| Raf fiyatını en büyük, düz ve çizgisiz göster | Üyelik fiyatını raf fiyatının yerine ya da ondan büyük yazma |
| Üyelik fiyatını etiketiyle aynı kutuda göster | Üyelik fiyatını etiketsiz, üstü çizili fiyatın yanında ya da indirim rozetiyle gösterme |
| Birim notunu ("kg fiyatı") ait olduğu her fiyata yapıştır | Birim notunu marka satırına, kartın başka bir köşesine koyma |
| Seçim ekranını "Geri"li tam ekran aç | Sürükleyerek kapanan alt sayfa, açılır menü kullanma |
| Fiyatı `ProductFacts` ile göster | Yeni bir ekranda fiyatı elle, başka boyut ya da renkle yeniden çizme |
| Aramada hangi marketlere bakıldığını adıyla söyle | "Bütün marketlerde en ucuz", "en uygun fiyat" gibi kanıtlanamayan söz yazma |
| Sonuçta marketi ve broşür tarihini her kartta göster | Fiyatı kaynağı ve tarihi olmadan gösterme |
| Örnek sözcüğü yalnızca sonucu varsa öner | Basınca "bulunamadı" çıkacak öneri gösterme |
| Broşürden okunan fiyatı "Broşürden okundu" satırıyla, ürün başına göster | Etiketi dosya başına koyma; okunan fiyatı etiketsiz, yazılı fiyatın görünüşüyle gösterme |
| Okunan fiyatın düğmesine sayfa numarasını yaz ("Broşürde gör, sayfa 3") | Kanıtı (sayfayı) bir menünün ya da gizli hareketin arkasına koyma |

## 13. Açık noktalar ve sonraya kalanlar

- **"Bu hafta" sırası:** veri katmanı (`groupBrochures`) en yeni başlayanı üstte verir; market
  ekranı yeniden sıralamaz (kural `lib/data/README.md` içinde).
- **"Yeni" rozeti:** kazıyıcı ilk kez çalıştığında bütün broşürler "Yeni" görünür (hepsi aynı gün
  görülmüş olur); birkaç gün içinde kendiliğinden düzelir.
- **Sayfa seçicide küçük görsel yok** (bölüm 8); kazıyıcı küçük sayfa görseli üretirse eklenebilir.
- **Üyelik fiyatı yalnızca Migros örneğiyle denendi** ("Money ile"); başka bir marketin etiketi çok
  uzunsa kutu kendi içinde sarar (testte 320 dp + yazı ölçeği 2,0 ile denendi).
- **Kapak görseli yüklenemezse** yer tutucu kalır; ekran yeniden açılınca tekrar denenir (listede
  kart başına "Tekrar dene" bilerek yok).
- **A101 ve Watsons logoları** yok (siteleri otomatik isteği engelliyor); dosya eklenirse
  `chain_logos.dart`'a bir satır yeter.
- **Örnek veri:** `assets/sample/catalog.json` içinde BİM ve Watsons sayfaları ile Migros kapağı
  gerçek adreslerdir (13 Kasım 2026'da alındı, zamanla silinebilir); "18 Kasım Çarşamba" broşürünün
  görselleri gerçekte 17 Kasım Salı afişleridir (o gün için yayınlanmış görsel yoktu). Şok ve Migros
  sayfaları göreli yoldur, uygulamaya gömülü değildir; "sayfa açılamadı" durumunu göstermek için
  öyle bırakıldı.
- **Bildirim (bölüm 16):** Teklifin "bir kez" kaydı
  şimdilik arayüz tarafında (`notification_offer_store.dart`, `shared_preferences`); veri katmanı bir
  yer verirse oraya taşınabilir. Gerçek izin penceresi ve bildirim cihazda denenmedi.
- **Arama, sözcük sonu yumuşamasını bilmiyor:** "ekmek" yazınca "Tam Buğday Ekmeği", "tavuk" yazınca
  "Köy Tavuğu" bulunmuyor (k → ğ, p → b, ç → c, t → d). "Bulunamadı" iletisi bu yüzden somut bir yol
  gösterir ("ekmek" yerine "ekme"). Asıl çözüm veri katmanındadır (istek iletildi); gelince ileti
  sadeleştirilebilir.
- **Arama sırası raf fiyatına göredir, birim fiyata göre değil:** 200 ml süt 1 L sütün üstünde çıkar.
  Sonuçların üstünde "Paket boyları farklı olabilir" yazar; birim fiyat hesaplamak ürün eşleştirme
  gerektirir ve bilerek yapılmadı (yanlış hesap, eksik bilgiden kötüdür).
- **Arama yalnızca fiyat listesi olan broşürlerde çalışır**: marketin yazılı listesi (BİM, Migros) ya da
  sayfalardan okunan fiyatlar (Şok, Hakmar; bölüm 17). A101, Gratis, CarrefourSA (web görünümü) ve henüz
  okunmamış broşürler aranmaz; ekran bunu her durumda söyler. Bir marketin ürün dosyası indirilemezse o market sessizce listeden düşer
  (veri katmanı hangisinin eksik olduğunu bildirmiyor; istek iletildi).
- **Broşürden okunan fiyatlar canlı veriyle denenmedi** (ilk gerçek okuma 17 Kasım 12:17 çalışmasında);
  örnek veride 4 ürün var. Uzun bir listede (30+ ürün) her kartta satır + düğme kartları uzatır;
  canlı veriyle bakılmalı.
- **Arama dizini okunmuş fiyatı kendisi söylemiyor:** yazmadan önceki fiyat notunun hangisi olacağı
  (bölüm 15) katalogdan çıkarılıyor (aranan bir markette okunmuş listeli broşür var mı). Veri katmanı
  `SearchIndex`'e bu bilgiyi eklerse oraya taşınmalı (istek iletildi).
- **Macrocenter** katalogda renksiz geliyor ve `chainPlateColors` içinde yok; ad kartı sakin yeşil
  (`primarySoft`) zeminle görünür.

## 14. Fiyatlar: raf fiyatı, eski fiyat, üyelik fiyatı, birim notu

Projenin en büyük korkusu teyzeye yanlış fiyat göstermektir. Bir üründe üç ayrı fiyat bulunabilir;
her birinin **kendine ait, başkasıyla karışmayan** bir görünüşü vardır
(`lib/features/products/product_card.dart`).

| Fiyat | Anlamı | Görünüşü |
|---|---|---|
| **Raf fiyatı** (`price`) | Bugün herkesin ödediği | Kartın en büyük rakamı (`AppType.price`, 28), düz mürekkep, çerçevesiz, **asla üstü çizili değil**; her kartta aynı yerde |
| **Eski fiyat** (`oldPrice`) | Artık geçerli olmayan | Küçük (18), soluk, **üstü çizili**, raf fiyatının yanında; yanında kırmızı "%20 indirim" rozeti |
| **Üyelik fiyatı** (`memberPrice`) | Yalnızca kart sahibinin ödediği | Raf fiyatının hemen altında, **yeşil çerçeveli kutu** içinde: üstte kart simgesi + etiket ("Money ile"), altında fiyat (`AppType.memberPrice`, 24) |

**Hangisi baskın: raf fiyatı en büyük rakam, üyelik fiyatı en renkli öğe.** Gerekçe:
- Kartsız teyze kartın en büyük rakamını okur; o rakam her zaman onun ödeyeceği fiyat olmalı. Tersi
  (büyük üyelik fiyatı) kasada daha yüksek bir fiyatla karşılaşması demek; kaçınılacak hata bu.
- Kartlı teyze için haber üyelik fiyatıdır; onu kaçırmaması boyutla değil **renk ve çerçeveyle**
  sağlanır: kartta renkli çerçevesi olan tek öğe o kutudur.
- Raf fiyatı bütün kartlarda (üyelik fiyatı olsun olmasın) aynı yerde ve aynı biçimdedir; liste
  aşağı doğru taranırken "herkesin fiyatı" sütunu hiç bozulmaz.

Kurallar:
- Üyelik fiyatı **asla etiketsiz** görünmez. Etiket ile fiyat aynı kutunun içindedir, aralarında
  boşluk yoktur, ekran okuyucu ikisini tek cümle okur ("Money ile: 77,95 ₺"). Etiketi olmayan üyelik
  fiyatını model zaten düşürür; kart da göstermenin bir yolunu aramaz (testli).
- Üyelik fiyatı **asla raf fiyatının yerine geçmez**, ondan büyük yazılmaz, üstü çizili fiyatla yan
  yana durmaz. Raf fiyatının üstü çizilmez: o "eski fiyat" değil, kartı olmayanın bugünkü fiyatıdır.
- "%… indirim" rozeti yalnızca eski fiyat → raf fiyatı içindir (`discountPercent`); üyelik fiyatı
  için indirim yüzdesi hesaplanmaz ve gösterilmez.
- Kutu yeşildir (`primarySoft` zemin, `primary` çerçeve), kırmızı değil: kırmızı (`fresh`) "Yeni" ve
  indirimin rengidir; üyelik fiyatı bir indirim rozeti gibi görünürse raf fiyatı "eski fiyat" sanılır.
- Üç fiyat birden varsa sıra: üst satırda raf fiyatı + eski fiyat + indirim rozeti, altında üyelik
  kutusu. Dar ekranda ve büyük yazıda satırlar sarar, kutu küçülmez.

**Birim notu** (`quantityText`, ör. "kg fiyatı"): fiyatın neyin fiyatı olduğunu söyler; 1.799,00 ₺'nin
paket fiyatı sanılmaması gerekir.
- Not, ait olduğu fiyatın **hemen sağında, aynı satırda** durur (`PriceWithUnit`); sığmazsa fiyatın
  hemen altına iner ama araya başka bir şey girmez. Ekran okuyucu "1.799,00 ₺, kg fiyatı" okur.
- Üyelik fiyatı da aynı birim içindir; not **kutunun içinde de yinelenir** ("1.499,90 ₺ kg fiyatı").
- Not kalın ve mürekkep rengindedir (soluk değil): fiyatın parçasıdır, ek bilgi değil.
- `quantityText` boşsa hiçbir şey çizilmez, boşluk kalmaz. Eski veride "700 g", "5 L" gibi değerler
  gelirse aynı yerde gösterilir ("149,50 ₺ 700 g"); raf etiketlerindeki okuyuşla aynıdır.
- Marka artık tek başına ad satırının altındadır; miktar marka satırına yazılmaz.

## 15. Ürün arama ("Broşürlerde ara")

Teyze ürünün adını yazar ("süt", "çay"); **fiyat listesi olan** bütün güncel broşürlerdeki eşleşen ürünler,
ucuzdan pahalıya sıralı gelir. Fiyat listesi ya marketin kendi yazdığıdır (BİM, Migros) ya da broşür
sayfalarından otomatik okunmuştur (Şok, Hakmar); ikincisi her kartta "Broşürden okundu" satırıyla
ayrılır (bölüm 17). Ürün eşleştirme yoktur. Kod `lib/features/search/`, veri `searchIndexProvider`
(`lib/data/search.dart`).

**Ana kural: ekran bildiğinden fazlasını söylemez.** Arama bütün marketleri kapsamaz (web görünümündeki
marketler ve henüz okunmamış broşürler aranmaz), fiyat her gün geçerli değildir, paketler aynı boyda
değildir, okunan fiyat bir makine okumasıdır. Bunların hepsi ekranda yazar.

### Akış

```
Ana ekran "Ürün ara" → Arama (klavye açık) → yaz ya da örnek sözcüğe bas → sonuçlar
   → karta bas → Broşür: ürünün basıldığı sayfa (sayfası biliniyorsa)
                         ya da ürün listesi, "Aradığınız ürün" en üstte
   → "Geri" → sonuçlar (yazı ve liste yerinde)
```

### Arama ekranı

- **Üst çubuk** tek satırdır (`keepOnOneRow`): klavye açıkken altta kalan her dp sonuçlarındır.
- **Yazı alanı** (`SearchField`) çubuğun altında sabittir, kaymaz. En az 64 dp, 21 sp yazı, kalın çerçeve;
  klavye üstündeyken çerçeve yeşile döner ve kalınlaşır (çerçeve yazının üstüne çizilir, yazı yerinden
  oynamaz). Ekran açılınca klavye kendiliğinden gelir. Çok büyük yazıda baştaki büyüteç simgesi kalkar
  (harflere yer açmak için).
- **"Yazıyı sil"** düğmesi (56 dp, ×) yalnızca silinecek yazı varken görünür; basınca alan boşalır ve
  klavye geri gelir.
- **Yazdıkça arar**; "Ara" düğmesi yoktur (basılacak bir adım daha, unutulacak bir adım daha). Klavyenin
  kendi "Ara" tuşu ve listeyi kaydırmak klavyeyi kapatır.
- **En az iki harf** (`AppSize.searchMinLetters`): tek harfte yüzlerce ilgisiz ürün gelir; onun yerine
  "En az iki harf yazın." yazar.

### Yazmadan önce

1. "Ne arıyorsunuz?" + tek cümle açıklama.
2. **Örnek sözcükler**: "Süt", "Çay", "Yağ"… büyük düğmeler (56 dp, çerçeveli; küçük "çip" değil).
   Yazmak zor gelen için tek dokunuşla arama. Liste `searchExamples` metnindedir ve **yalnızca o hafta
   sonucu olanlar** gösterilir (en çok 6): basınca "bulunamadı" çıkacak bir öneri küçük bir yalandır.
   Basınca klavye kapanır ki sonuçlar arkasında kalmasın.
3. **"Arama yapılan marketler"**: `SearchIndex.chains` içindeki marketlerin logo / ad plakaları ve altında
   "Diğer marketlerin broşürlerinde henüz arama yapılamıyor. Onlara ana ekrandan bakabilirsiniz."
   (Eskiden "resim olarak yayınlıyor" diyordu; Şok ve Hakmar okununca bu yanlış oldu. Yeni cümle A101,
   Gratis, CarrefourSA ve henüz okunmamış broşürler için doğrudur.)
4. Fiyat notu (`InfoNote`, anahtar `search-price-note`). İki biçimi var:
   - Okunmuş fiyat yoksa: "Fiyatlar broşürde yazdığı gibidir; broşürün tarihlerinde geçerlidir."
   - Okunmuş fiyat görünebiliyorsa: "Fiyatlar broşürün tarihlerinde geçerlidir. “Broşürden okundu”
     yazanları broşür sayfasından otomatik okuduk; dokununca o sayfa açılır." "Yazdığı gibidir" bu
     biçimde **yoktur**: okunan fiyat için bunu biz garanti edemeyiz.

   Yazmadan önce: aranan bir markette okunmuş listeli broşür varsa ikincisi. Sonuçlarda: ekrandaki
   sonuçlardan biri okunmuşsa ikincisi (yalnızca BİM sütü arayan, görmeyeceği bir etiketin açıklamasını
   okumaz).

### Sonuçlar

- Başlık: "24 ürün bulundu" (ekran okuyucuya canlı bölge olarak duyurulur), altında "En ucuzu en üstte.
  Paket boyları farklı olabilir." ve fiyat notu. Yazı ölçeği 1,3'ün üstündeyse fiyat notu listenin
  **sonuna** iner: yoksa notlar ekranı doldurur, ilk sonuç görünmez (320 dp + ölçek 2,0'da denendi).
- Liste sonunda her zaman: "Arama yapılan marketler: BİM, Migros. Diğer marketlerin broşürlerinde henüz
  arama yapılamıyor." "En ucuzu" sözü ancak bu cümleyle birlikte doğrudur.
- **Sıra** veri katmanından gelir: raf fiyatı artan. Üyelik fiyatı sırayı **etkilemez** (kartsız teyzeye
  göre sıralanır); ekran yeniden sıralamaz.
- **Sonuç kartı** (`SearchResultCard`), tamamı tek düğme:
  - Üstte `ProductFacts`: fotoğraf (varsa), ad, marka, raf fiyatı (+ birim notu), eski fiyat ve indirim
    rozeti, üyelik etiketi. Bölüm 14 aynen geçerlidir; kart fiyatı kendi çizmez.
  - İnce çizgi, altında **kaynak satırı**: market plakası (logo ya da ad kartı, 92 × 48), yanında market
    adı **yazıyla** ve broşürün tarih aralığı ("12–25 Kasım"), en sağda "Aç ›" işareti (`OpenCue`).
    Ad yazıyla da durur, çünkü küçük plakadaki logo tanınmayabilir ve plaka yazı ölçeğiyle büyümez.
  - Broşür **henüz başlamadıysa** (`valid_from` bugünden sonra) tarihin altında sakin sarı "Henüz
    başlamadı" etiketi çıkar; fiyat bugün geçerli değildir ve kart bunu söylemek zorundadır.
  - Dar kartta (320 dp'den dar) ya da çok büyük yazıda "Aç ›" kaynak satırının altına iner.
  - Okunmuş fiyatta `ProductFacts` fiyatın altına "Broşürden okundu" satırını kendisi koyar; kartta ayrı
    bir düğme yoktur (kartın tamamı zaten o sayfayı açar).
  - Ekran okuyucu tek cümle okur: ad, marka, fiyat (birimiyle), eski fiyat, "Money ile: …", (Broşürden
    okundu), market, tarih, (henüz başlamadı), "Broşürde görmek için dokunun".

### Sonuca basınca

- Ürünün sayfası biliniyorsa (`pageIndex`, broşürde sayfa var: BİM; okunmuş fiyatta her zaman) broşür
  **o sayfada** açılır. Basılı
  sayfa fiyatın en sağlam kanıtıdır; "Ürünler" sekmesine geçilirse ürün orada da en üsttedir.
- Sayfa bilinmiyorsa (Migros: yalnızca ürün listesi) ürün listesi açılır; en üstte **"Aradığınız ürün"**
  başlığı ve yeşil çerçeveli kart, altında "Bu broşürdeki bütün ürünler" ile listenin tamamı (ürün kendi
  yerinde yeniden görünür). Listeyi ürüne kaydırmak yerine ürünü üste almak seçildi: kayan liste yaşlı
  kullanıcıyı şaşırtır, değişken yükseklikli kartlarda da hedefi tutturmak güvenilir değildir.
- Ürün o broşürün listesinde artık yoksa (dosya arada değişmişse) hiçbir şey üste alınmaz: eski bir
  fiyatı "aradığınız ürün" diye göstermektense göstermemek.
- "Geri" her zaman sonuçlara döner; araya başka ekran girmez.

### Bulunamadı, bekleme, internet yok

- **Bulunamadı:** "“kivi” bulunamadı", altında ne denenebileceği (sözcüğün yalnızca başını yazmak) ve
  hangi marketlere bakıldığı, bakılamayanların da olduğu. Büyük "Başka ürün ara" düğmesi alanı boşaltıp
  klavyeyi geri getirir. "Hiçbir markette yok" **denmez**; bilinen yalnızca aranan broşürlerde olmadığıdır.
- **Hazırlanıyor:** halka + "Broşürlerdeki ürünler hazırlanıyor…". Alan bu sırada yazılabilir; dizin
  gelince sonuçlar kendiliğinden görünür.
- **İnternet yok, kayıt var:** sakin şerit; arama elde olanlarla çalışır.
- **İnternet yok, kayıtlı ürün listesi yok** ya da katalog hiç alınamadı: tam alan "Arama şu an
  yapılamıyor" + ne yapılacağı + "Tekrar dene".
- **Aranabilecek fiyat listesi yok:** "Şu an aranabilecek broşür yok" + "Broşürlerin fiyatları
  hazırlanınca burada arayabilirsiniz. O zamana kadar broşürlere ana ekrandan bakabilirsiniz." (Eskiden
  "marketler fiyatlarını yazı olarak yayınlayınca" diyordu; artık fiyat okunarak da gelebiliyor.)
- Arka plandaki sessiz katalog yenilemesi sonuçları silmez (`skipLoadingOnReload`).
- Bu ekranda hareket yoktur (bekleme halkası dışında); "hareketi azalt" için kapatılacak bir şey kalmaz.

### Doğrulama

`flutter test`: 299 geçiyor (2 araç testi bilerek atlanır); `flutter analyze` temiz.
Ekran görüntüleri: bkz. "Durum" bölümünün altındaki not.

## 16. Yeni broşür bildirimi

Teyze "Sık baktıklarım"a yıldız koyduğu marketler yeni broşür çıkarınca telefonuna kısa bir bildirim
gelsin ister. Kod `lib/features/notifications/`, veri `notificationsProvider` ve
`notificationTapProvider` (`lib/data/notifications.dart`, veri katmanının).

**Ana kural: sor, bir kez sor, sonra sus.** Bildirim izni bir rica; ısrar edilen bir rica güveni
bozar. Teklif kendiliğinden **en fazla bir kez** gelir; sonrası hep görünür bir düğmenin işidir.

### Nerede

- **Ana ekranda, "Sık baktıklarım" kartlarının hemen altında** (`NotificationControl`), "Diğer
  marketler" başlığının üstünde. Gerekçeler:
  - Ana ekranın menüsü yok (bilerek); ayarlar ekranı olmadığı için saklanacak bir yer de yok.
  - Bildirim yıldızlı marketler içindir; düğme konuştuğu şeyin yanında durur. Favoriler en üstte
    olduğu için düğme çoğu telefonda ilk ekranda görünür.
  - **Favori yokken hiç görünmez:** haber verilecek market yokken düğme boş bir söz olur. Favori
    yokken ızgaranın altındaki yıldız ipucu zaten ilk adımı öğretir.
- **İlk yıldızın hemen ardından teklif penceresi** (`offerNotificationsAfterFirstFavorite`). En
  doğru an budur: kullanıcı az önce "bu marketi takip ediyorum" dedi. Ana ekrandaki ve market
  ekranındaki yıldızın ikisi de bu anı yakalar. Koşullar: favoriler boştan bire çıktı, bildirim
  durumu `off`, teklif daha önce yapılmadı. Pencere açıldığı anda "yapıldı" diye kaydedilir; cevap ne
  olursa olsun bir daha kendiliğinden açılmaz. Kullanıcı düğmeyle açar ya da kapatırsa da kaydedilir.

### Teklif penceresi (`NotificationOfferDialog`)

Telefonun kendi izin penceresinden **önce** ne olacağını tek bir sade cümleyle söyler:

```
★ Şok en üste alındı.              (yalnızca ilk yıldızdan gelince)
(zil)
Yeni broşür çıkınca haber verelim mi?
Şok yeni broşür çıkarınca telefonunuza kısa bir bildirim gelir.
ⓘ Telefon izin sorarsa “İzin ver”e dokunun.
[ 🔔 Evet, haber ver ]              birincil, 64 dp, tam genişlik
[ Şimdi değil ]                     çerçeveli, 64 dp, tam genişlik
```

- **Pencere, tam ekran değil:** bu bir seçim listesi değil, o ana bağlı tek bir evet / hayır
  sorusu; arkada ana ekranın görünmesi "nerede olduğumu" korur. Yine de bölüm 12'deki kural
  geçerlidir: sürükleyerek kapanmaz, alt sayfa değildir.
- **Pencerenin dışına dokunmak bir şey yapmaz** (`barrierDismissible: false`): kazara bir dokunuş
  soruyu cevaplamamalı. Telefonun geri tuşu "Şimdi değil" demektir.
- **"İzin ver" notu:** telefonun izin penceresi yaşlı kullanıcıyı ürkütür (başka renk, başka dil);
  hangi düğmeye basacağını önceden bilmek bu korkuyu alır. Android'de düğmenin Türkçe adı budur.
- İlk yıldızdan gelince pencerenin ilk satırı yıldızın ne yaptığını söyler ("Şok en üste alındı.");
  alttan çıkan ileti bu yüzden gösterilmez (pencerenin arkasında okunmazdı).
- Yazılar sola dayalıdır (uzun ortalı metin zor okunur); pencere uzun gelirse kendi içinde kayar.
- Zemin karartması `scrim` rengidir (açık: mürekkep %60, koyu: siyah %70). Belirme kısa bir solma;
  "hareketi azalt" açıkken anında açılır.
- "Evet" → `turnOn()` → telefon izin sorar. Sonuç alttan iletiyle söylenir: açıldıysa "Tamam. Yeni
  broşür çıkınca haber vereceğiz.", telefon izin vermediyse "Telefon izin vermediği için bildirim
  açılmadı.", başka bir aksilikte "Bildirim şu an ayarlanamadı. Biraz sonra tekrar deneyin."

### Durumlar

| Durum | Görünüş |
|---|---|
| `unavailable` (ya da durum henüz bilinmiyor) | **Hiçbir şey.** Ana ekran bildirim yokmuş gibi, aralık bile eklenmez; ilk yıldızda pencere açılmaz |
| `off` | Tek satır düğme (en az 64 dp): solda yumuşak yeşil karede boş zil, kalın "Yeni broşür çıkınca haber ver", altında "Bildirim şu an kapalı", sağda ›. Basınca teklif penceresi |
| `on` | Yumuşak yeşil panel: dolu yeşil karede çalan zil, "Yeni broşür bildirimi açık", "Şok ve BİM yeni broşür çıkarınca telefonunuza bildirim gelir." ve altında çerçeveli "Bildirimi kapat" (56 dp) |
| `blockedBySystem` | Sakin krem panel: üstü çizili zil, "Bildirimler telefonda kapalı", neden gerektiği tek cümle; altında tam genişlikte, 64 dp, yumuşak yeşil **"Telefon ayarlarını aç"**, onun altında çerçeveli "Elle nasıl açılır?" (basınca numaralı üç adım açılır, düğme "Adımları gizle" olur) |

- **Kapalı = basılır görünüş.** "Krem zemin + koyu çerçeve" bu uygulamada her yerde "basılır" demektir
  (bölüm 8); "Ürün ara" ile aynı aile. Zil karesi dolu yeşil değil yumuşak yeşildir: ana ekranın asıl
  işi market seçmek, bu bir teklif.
- **Açık = onay, düğme değil.** Panelin kendisi basılmaz; yeşil zemin "tamam, açık" der. Hangi
  marketler için açık olduğu adıyla yazılır (dört ve üstünde "Sık baktığınız 5 market"); nasıl
  kapatılacağı da görünür bir düğmedir. Kapatmak için "emin misiniz?" sorulmaz: geri açmak tek dokunuş.
- **Telefonda kapalı = sarı değil.** Kullanıcı izni bilerek vermemiş olabilir; ana ekranda kalıcı bir
  sarı uyarı kutusu sürekli "düzelt beni" der ve dırdır olur. Krem panel durumu söyler, adımlar bir
  düğme uzaklıktadır.
- **"Telefon ayarlarını aç" asıl yoldur.** `openSystemSettings()` Android'de doğrudan bu uygulamanın
  bildirim sayfasını açar (orada tek bir anahtar kalır); üç adımı okuyup uygulamak yerine bir dokunuş.
  Büyük ve tam genişliktedir ama **dolu yeşil değil yumuşak yeşildir** (`tonal`): ana ekranın tek işi
  market seçmek, bu bir durum paneli.
- **Yazılı adımlar yedektir.** "Elle nasıl açılır?" düğmesinin arkasında durur. Ayar sayfası açılamazsa
  (`false`) adımlar kendiliğinden açılır ve alttan ileti söyler: "Telefonun ayarları açılamadı. Aşağıdaki
  adımları izleyin." Düğmeye yeniden basmak adımları kapatmaz.
- **Dönüşte kendiliğinden açık.** Kullanıcı ayarlardan izin verip uygulamaya dönünce veri katmanı izni
  yeniden denetler, panel kendiliğinden yeşil "açık" paneline döner; ekranın yapacağı bir şey yok.
  `blockedBySystem` uygulama yeniden açılınca da sürer.
- Adımlar: "1 Telefonun Ayarlar uygulamasını açın." "2 “Uygulamalar”a, sonra “Çarşı Pazar”a
  dokunun." "3 “Bildirimler”e dokunup açın, sonra buraya geri dönün." Numara yumuşak yeşil karede;
  ekran okuyucu "Adım 1: …" okur. Ok karakteri kullanılmaz (bölüm 3).
- Panelin içindeki düğme metnin **altındadır**, yanında değil: büyük yazıda yan yana düğme sözcükleri
  sıkıştırır. Yazı ölçeği 1,3'ün üstünde bu paneldeki düğmelerin simgesi kalkar, adım numarası da
  cümlenin üstüne geçer: 320 dp + 2,0'da yanlarında kalınca "ayarlarını" ve "uygulamasını" ortadan
  bölünüyordu (ekran görüntüsünde görüldü).
- Yazı ölçeği 1,3'ün üstündeyse (`useStackedBars`) zil karesi sözcüklerin **üstüne** geçer ve sözcükler
  bütün genişliği alır; yanında kalınca 320 dp + 2,0'da "Bildirimler" ortadan bölünüyordu (denendi).
  Kapalı düğmenin › işareti de bu ölçekte kalkar ("Ürün ara" ile aynı).
- Durum henüz bilinmiyorken (açılışta Firebase hazırlanırken) de hiçbir şey çizilmez; bilinince denetim
  belirir. İlk yıldızda teklif, durumu en çok 2 sn bekler; bilinmezse teklif yapılmaz (ve "yapıldı"
  sayılmaz), yıldızın iletisi beklemez.

### Bildirime dokununca (`NotificationTapHandler`)

Uygulamanın ilk sayfasını sarar (`app.dart`); uygulama bildirime dokunularak açıldıysa da ilk kareden
dinler. Katalog henüz yükleniyorsa yüklenmesini bekler. Bildirim anahtarını (`notificationsProvider`)
da açılışta başlatır: durum ilk yıldıza kadar bilinir ve yıldızlı marketlerin abonelikleri, ekranda
denetim görünmese de güncel kalır.

- Bildirim bir broşür adı veriyorsa ve broşür katalogda **o markete ait** olarak duruyorsa: **broşür
  doğrudan açılır.** Altına market ekranı sıkıştırılmaz; "Geri" kullanıcının bildirimden önce
  bulunduğu yere döner (ilke 4: görmediği ara ekran yığına girmez).
- Broşür yoksa (süresi dolmuş, silinmiş) ya da başka bir markete aitse: **market**, ana ekrandaki
  kartı nasıl açıyorsa öyle (`openChain`: market ekranı, tek broşürü, ya da sitesi).
- Market katalogda yoksa ya da katalog hiç alınamadıysa: ana ekranda kalınır; ana ekran durumu
  (internet yok vb.) zaten kendisi söyler.
- Her dokunuş ayrı bir olaydır: aynı bildirime ikinci kez dokunmak ekranı yeniden açar.

### Yap / yapma

| Yap | Yapma |
|---|---|
| Teklifi ilk yıldızın ardından bir kez yap | Açılışta, her yıldızda ya da "kapalı" diye tekrar tekrar sor |
| Telefonun izin penceresinden önce ne olacağını tek cümleyle söyle | Hiçbir şey demeden telefonun izin penceresini aç |
| Açık durumu marketlerin adıyla doğrula, kapatma düğmesini göster | Yalnızca bir anahtar (switch) koy; ne açık, kimin için belli olmasın |
| `unavailable` iken hiçbir şey çizme | Kullanılamayan bir özellik için gri düğme ya da açıklama göster |
| Telefonda kapalıyken önce ayar sayfasını aç, adımları yedek tut | Sarı / kırmızı kalıcı uyarı kutusu koy; yalnızca "ayarlara gidin" deyip yolu göstermeme |

### Doğrulama

Testler `test/ui/notifications_test.dart`: her durum, teklifin bir kez gösterilmesi (geri tuşu, dışarı
dokunma, ikinci yıldız, daha önce yapılmış, `on` / `blocked` / `unavailable` iken açılmaması, market
ekranından), telefonun izni reddetmesi, "Telefon ayarlarını aç" (açıldı / açılamadı → adımlar), bildirime dokununca
açılan ekran (broşür, olmayan broşür, başka marketin broşürü, bilinmeyen market, aynı bildirime ikinci
dokunuş), "hareketi azalt", ad listesi; yazı ölçeği 1,0 / 1,3 / 2,0
× açık / koyu × 411 / 320 dp taşma denemeleri (üç durum + pencere). 78 test.

`flutter test`: 413 geçiyor, 11 atlanıyor (2 simge + 9 ekran görüntüsü aracı; bilerek);
`flutter analyze` temiz. Ekran görüntüleri: "Durum" bölümünün altındaki D4 notu.

## 17. Broşürden okunan fiyatlar ("Broşürden okundu")

Şok ve Hakmar fiyatlarını yazı olarak yayınlamıyor; kazıyıcı broşür sayfalarını bir yapay zekâ modeliyle
okuyor (ölçümde fiyat doğruluğu ~%100, ama yine de makine okuması). Kullanıcı kararı: bu fiyatlar
gösterilir, **her biri etiketiyle ve broşürün o sayfasına giden bağlantıyla.** Veri: `product.isOcr`,
`hit.isOcr`, `product.pageIndex` (okunmuş fiyatta her zaman dolu), `brochure.hasProductList`
(`lib/data/README.md`, "OCR ürünleri").

**Ana kural: okunan fiyat marketin yazdığı fiyatla karışmaz, ama korkutmaz da.** Teyze iki şeyi bilmeli:
bu fiyatı market yazmadı, biz okuduk; emin olmak isterse broşürdeki sayfası bir dokunuş uzakta. "Yanlış
olabilir", "dikkat", sarı uyarı kutusu yok: ölçülen doğruluk buna gerek bırakmıyor ve ürküten bir etiket
fiyatın kendisinden daha çok dikkat çeker.

### Sözcükler

| Yer | Metin | Neden |
|---|---|---|
| Fiyatın altındaki satır (`ocrTag`) | **Broşürden okundu** | Kısa, gündelik: fiyatın nereden geldiğini söyler; "makine", "tahmini", "yanlış olabilir" gibi ürküten ya da teknik sözcük taşımaz. "Okundu" yazılı listeden ayırır. |
| Kartın düğmesi (`ocrShowOnPage`) | **Broşürde gör, sayfa 3** | Eylem önce (ne olacak), sayfa sonra (nereye). Sayı sonda olduğu için Türkçe ek hesaplanmaz ("3'te", "6'da"). "Sayfada göster"den farkı: burada kanıt asıl iştir, sayfa adıyla söylenir. |
| Listenin başı, bir kez (`ocrListNote`) | **Bu fiyatları broşür sayfalarından otomatik okuduk. Emin olmak için “Broşürde gör”e dokunun.** | "Otomatik" yalnızca burada, bir kez söylenir: dürüst olan bu, ama her kartta yinelenirse dırdır olur. İkinci cümle ne yapılacağını düğmenin adıyla söyler. "Kasada broşürdeki fiyat geçerlidir" **denmedi**: kasada neyin geçerli olduğunu biz bilemeyiz. |
| Aramadaki fiyat notu (`searchPriceNoteOcr`) | **Fiyatlar broşürün tarihlerinde geçerlidir. “Broşürden okundu” yazanları broşür sayfasından otomatik okuduk; dokununca o sayfa açılır.** | Etiketi açıklar ve kanıtın yolunu verir. Yalnızca okunmuş fiyat görünebiliyorsa çıkar (bölüm 15). |

### Ürün kartı (`ProductCard`, `ProductFacts`, `OcrSourceTag`)

```
Lastik                              ad
139,00 ₺ 2 cm                       raf fiyatı + birim / miktar (bölüm 14, değişmedi)
(tarama) Broşürden okundu           OcrSourceTag: fiyatın hemen altı, sol kenarı fiyatla aynı
[ (kitap) Broşürde gör, sayfa 2 ]   yumuşak yeşil düğme, en az 56 dp
```

- **Satır; rozet ya da düğme değil.** Soluk mürekkep (`inkSoft`, yüzeyde 7:1 üstü), kalın 18 sp, solda
  "taranmış sayfa" simgesi (`document_scanner_outlined`). Zemin ve çerçeve **yok**: bu uygulamada dolu ya
  da çerçeveli yuvarlak kutu "basılır" demektir ve hemen altında gerçek bir düğme durur. İlk denemede
  krem zeminli kutu + kitap simgesi kullanıldı; emülatörde altındaki "Broşürde gör" ile iki düğme gibi
  göründü, değiştirildi.
- **Kırmızı ya da sarı değil.** Kırmızı "Yeni" / indirim, sarı "henüz başlamadı" ve durum şeritleri içindir;
  okunan fiyat bir uyarı değil, bir köken bilgisidir.
- **Yeri sabit:** fiyat satırının (raf fiyatı + eski fiyat + indirim) hemen altında, üyelik kutusundan önce.
  Etiket fiyata aittir; kartın başka köşesinde fiyattan kopar.
- **Ürün başına**, dosya başına değil: yazılı bir listede tek bir okunmuş ürün de etiketini alır. Yazılı
  fiyatlı kartlar (BİM, Migros) hiç değişmedi.
- **Miktar görünür:** `quantity_text` ("2 cm", "5 L", "6 kg") fiyatın yanında, bölüm 14'teki birim notu
  yerinde durur. Aynı adlı iki "Lastik" böyle ayrılır; ad satırına ayrıca eklenmedi (aynı bilgi iki
  yerde kalabalık eder).
- **Düğme** `AppButton` tonal, `minHeight: AppSize.touch`; büyük yazıda iki satıra sarar ("Broşürde gör, /
  sayfa 1"), kesilmez. Basınca "Broşür" sekmesine geçilir ve o sayfa açılır.
- **Ekran okuyucu:** kartın bilgisi tek düğüm, sırası: ad, marka, fiyat (birimiyle), eski fiyat, indirim,
  "Broşürden okundu". Düğme ayrı düğüm: "Broşürde gör, sayfa 2".

### Ürün listesi ve broşür ekranı

- Okunmuş listesi olan broşürde (Şok, Hakmar) "Broşür | Ürünler" sekmeleri görünür
  (`brochure.hasProductList`; eskiden yalnızca yazılı liste için). Broşür sayfalarla açılır; liste ancak
  "Ürünler"e basılınca indirilir.
- Listede okunmuş fiyat varsa en üstte, ürün sayısının üstünde, **bir kez** `InfoNote` (`ocr-list-note`).
  Aramadan gelinip "Aradığınız ürün" gösteriliyorsa not onun da üstündedir.
- Yazı ölçeği 2,0'da ilk metin 7 satır tutup ilk ürünü ekrandan itiyordu; iki kısa cümleye indirildi, şimdi
  ilk kart ve düğmesi ilk ekranda (ekran görüntüsü `74`).
- Sekmeler eklenince 320 dp + 2,0'da sayfa kâğıdı küçüldü ve "Sayfa yükleniyor…" yazısı taştı
  (`zoomable_page.dart`, `_PageLoading`): yazı artık sığmazsa solarak çekilir, halka her zaman görünür.

### Market ekranı (broşür kartı)

Kartta "4 sayfa · 14 ürün" yalnızca marketin yazılı listesi için yazar; **okunmuş fiyatlar sayılmaz**, kart
"4 sayfa" der. Gerekçe: okunan sayı marketin broşüre koyduğu ürün sayısı değil, okumanın bulabildiği
sayıdır; "38 ürün" bir eksiksizlik sözü gibi okunur ve okuma ilerledikçe değişebilir. Listenin varlığı
broşür açılınca sekmeden zaten görünür. Veri katmanından sayı istenmedi.

### Arama

- Sonuç kartında etiket `ProductFacts` üzerinden kendiliğinden gelir; karta basınca broşür o sayfada
  açılır (`openSearchHit`, `searchHitPage`; okunmuş fiyatta sayfa her zaman bilinir). "Ürünler" sekmesine
  geçilirse ürün "Aradığınız ürün" olarak en üstte, etiketiyle.
- Fiyat notu ve "Arama yapılan marketler" metinleri bölüm 15'te.

### Yap / yapma

| Yap | Yapma |
|---|---|
| "Broşürden okundu"yu fiyatın hemen altına sakin bir satır olarak koy | Etiketi rozet, düğme ya da renkli kutu yap; kırmızı / sarı kullan |
| "Otomatik okuduk"u listenin başında bir kez söyle | Her kartta "otomatik", "tahmini", "yanlış olabilir" yaz |
| Düğmede sayfa numarasını sona koy ("Broşürde gör, sayfa 3") | Sayıya Türkçe ek ekle ("3'te") ya da sayfayı söylemeden "Göster" de |
| Okunmuş fiyatları broşür kartında sayma | Okuma sayısını marketin listesiymiş gibi "38 ürün" diye göster |
| "Yazdığı gibidir" sözünü yalnızca yazılı fiyatlar için kullan | Okunan fiyat için "broşürde yazdığı gibidir" ya da "kasada geçerlidir" garantisi ver |

### Doğrulama

`test/ui/ocr_test.dart` (39 test): etiket yalnızca okunmuş fiyatta ve fiyatın altında, 18 sp, rozet değil;
yazılı kartta etiket yok ve "Sayfada göster" aynen; düğme sayfayı söylüyor, 56 dp, basınca çalışıyor;
ekran okuyucu etiketi fiyattan sonra okuyor; Şok broşüründe sekmeler, liste başında tek not, 4 etiket,
"2 cm" / "3 cm", "Broşürde gör, sayfa 4" → görüntüleyici 4 / 4; BİM listesinde not ve etiket yok; broşür
kartı okunmuş fiyatı saymıyor; aramada etiket, ekran okuyucu cümlesi, iki fiyat notu, sonuçtan 4 / 4 ve
"Ürünler"de en üstte etiketli ürün; metinlerde "resim" / "yazı olarak" kalmadı; yazı ölçeği 1,0 / 1,3 / 2,0
× açık / koyu × 411 / 320 dp taşma denemeleri (liste ve arama). `test/ui/support.dart`'taki sahte depo artık
okunmuş listeyi de veriyor; bu yüzden `search_test.dart`'ta Şok aranan marketler arasında (4 test buna göre
güncellendi). Ekran görüntüleri `70`–`75`: "Durum" bölümünün altındaki 3B.3 notu.
