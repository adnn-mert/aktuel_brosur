# Çarşı Pazar — tasarım sistemi

Bu belge arayüzün tek bağlayıcı kaynağıdır. Arayüze dokunan herkes (insan ya da model) önce bunu
okur, aynı dili sürdürür. Bir kural gerekçesiyle yazılmıştır; gerekçe geçersiz kalmadıkça kural
değişmez. Büyük görsel kararlar (renk, yazı tipi, logo) değiştirilmeden önce proje sahibine sorulur.

## Durum

Son güncelleme: 14 Kasım 2026. **D1 görevi tamamlandı**; sekiz dilimin hepsi bitti.

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
| Testler | `flutter test`: 80 veri + 79 arayüz testi geçiyor (2 araç testi bilerek atlanır) |
| Ekran görüntüleri | `design/screenshots/` (açık, koyu, büyük yazı, yakınlaştırılmış, uçak modu) |

Emülatörde (Medium_Phone) uçtan uca denenen akış: aç → market → broşür → + ile ve çift dokunmayla
yakınlaştır → büyütülmüşken kaydır (sayfa değişmedi) → okla sayfa değiştir → geri → favori işaretle →
uygulamayı kapat aç (favori üstte) → uçak modunda daha önce açılan broşür ve ürün listesi açıldı.
İki parmakla yakınlaştırma emülatörde `adb` ile üretilemediği için yalnızca widget testiyle doğrulandı
(`test/ui/viewer_test.dart`, "two fingers zoom the page and never turn it"); gerçek cihazda bir kez
elle denenmesi iyi olur. iOS tarafı (ad, simge, açılış zemini) Mac olmadığı için derlenip denenmedi.

Derleme notu: bu makinede `flutter build apk --debug` yalnızca şu ortam değişkeniyle çalışıyor
(boşluksuz, kısa bir klasör): `JAVA_TOOL_OPTIONS=-Djdk.net.unixdomain.tmpdir=C:\Users\Public\uds`.

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
| `price` / `priceOld` | Lexend 700 / 500 | 28 / 18 | Fiyat / üstü çizili eski fiyat (sabit genişlikli rakam) |
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
- Yeni logo eklemek: dosyayı `assets/logos/` altına koy, `chain_logos.dart` içine bir satır ekle.

## 7. Ekranlar ve akış

```
Açılış → Ana ekran ─┬─ (web görünümü zinciri) ───────────────→ Web görünümü
                    ├─ (tek broşürü olan market) ────────────→ Broşür
                    └─ Market ekranı → Broşür (sayfalar ⇄ ürün listesi)
```

**En az dokunuş kuralı:** bir marketin gösterilecek **tek** broşürü varsa (bu hafta + gelecek +
geçmiş toplamı 1) market ekranı atlanır, karta basınca broşür doğrudan açılır; "Geri" ana ekrana
döner. Birden fazla broşür varsa market ekranı açılır. Gerekçe: seçecek bir şey yokken seçim ekranı
göstermek boş bir adımdır; ama araya kullanıcının görmediği bir ekran sokup "Geri"yi oraya
düşürmek (ilke 4) daha kötüdür, o yüzden yalnızca gerçekten tek seçenek varken atlanır.

### Ana ekran
- Üstte logo + "Çarşı Pazar", altında tek soru: "Hangi markete bakalım?". Menü, sekme, arama yok.
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
- **Aşama 2 "ürün ara" girişi:** başlık ile ızgara arasına, tam genişlikte, 64 dp yüksekliğinde,
  içinde büyüteç ve "Ürün ara" yazan tek bir düğme olarak gelecek. Şimdi yok; yeri budur.

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
- Tek sütun büyük kartlar: ad (kalın), marka, miktar, büyük fiyat, varsa üstü çizili eski fiyat ve
  "%20 indirim" etiketi; ürün fotoğrafı varsa solda.
- Broşürde sayfa da varsa (`kind: both`) üstte iki büyük sekme: "Broşür" | "Ürünler". Sekme her
  zaman görünür; üründe sayfa numarası varsa "Sayfada göster" düğmesi o sayfayı açar.

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
| `ChainMark` | `chain_mark.dart` | Market logosu ya da ad kartı |
| `CatalogImage`, `CoverPlaceholder`, `catalogImageProvider` | `catalog_image.dart` | Katalogdaki her görsel (adres çözme + disk önbelleği burada) |
| `LogoMark`, `LogoPainter`, `LogoPalette` | `logo_mark.dart` | Uygulama logosu |

Ekrana özgü bileşenler: `ChainCard`, `ChainGrid` (ana ekran); `BrochureCard` (market ekranı);
`ZoomablePage`, `PageZoomController`, `ViewerControls`, `ModeTabs` (broşür); `ProductCard`,
`ProductList` (ürünler); `WebCatalogBar`, `WebCatalogError` (web).

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

## 13. Açık noktalar ve sonraya kalanlar

- **"Bu hafta" sırası:** veri katmanı (`groupBrochures`) en yeni başlayanı üstte verir; market
  ekranı yeniden sıralamaz (kural `lib/data/README.md` içinde).
- **"Yeni" rozeti:** kazıyıcı ilk kez çalıştığında bütün broşürler "Yeni" görünür (hepsi aynı gün
  görülmüş olur); birkaç gün içinde kendiliğinden düzelir.
- **Uzun kataloglarda sayfaya atlama:** Watsons 46 sayfa; şu an yalnızca oklarla ve kaydırarak
  gezilir. İleride "3 / 46" göstergesine basınca açılan büyük numaralı bir sayfa seçici düşünülebilir.
- **Kapak görseli yüklenemezse** yer tutucu kalır; ekran yeniden açılınca tekrar denenir (listede
  kart başına "Tekrar dene" bilerek yok).
- **A101 ve Watsons logoları** yok (siteleri otomatik isteği engelliyor); dosya eklenirse
  `chain_logos.dart`'a bir satır yeter.
- **Örnek veri:** `assets/sample/catalog.json` içinde BİM ve Watsons sayfaları ile Migros kapağı
  gerçek adreslerdir (13 Kasım 2026'da alındı, zamanla silinebilir); "18 Kasım Çarşamba" broşürünün
  görselleri gerçekte 17 Kasım Salı afişleridir (o gün için yayınlanmış görsel yoktu). Şok ve Migros
  sayfaları göreli yoldur, uygulamaya gömülü değildir; "sayfa açılamadı" durumunu göstermek için
  öyle bırakıldı.
- **Ürün arama (Aşama 2)** ve **bildirim izni ekranı (1I)** tasarlanmadı; yerleri bölüm 7'de.
