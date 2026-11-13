# Veri katmanı — tasarımcı kılavuzu

Ekranlar veriye **yalnızca Riverpod sağlayıcılarıyla** ulaşır. `http`, dosya sistemi, `rootBundle`
ve JSON ayrıştırma bu klasörün dışında kullanılmaz. Tek içe aktarma yeter:

```dart
import 'package:aktuel_brosur/data/data.dart';
```

Bu klasöre (`lib/data/`) arayüz kodu yazmayın; yeni bir veri ihtiyacı olursa worker'a iletin.

## Sağlayıcılar

| Sağlayıcı | Tür | Ne verir |
|---|---|---|
| `catalogProvider` | `AsyncValue<CatalogResult>` | Bütün katalog + tazelik bilgisi (`isStale`, `source`, `fetchedAt`). `.notifier.refresh()` yeniler. |
| `orderedChainsProvider` | `AsyncValue<List<Chain>>` | Ana ekran sırası: favoriler önce, sonra `sortOrder`, sonra Türkçe ad sırası. Web görünümü zincirleri de dahil. |
| `chainSummaryProvider(chainId)` | `AsyncValue<ChainSummary?>` | Kart özeti: `currentCount`, `upcomingCount`, `pastCount`, `isNew`, `isStale`, `isWebView`, `hasBrochures`, `latestFirstSeen`. |
| `chainProvider(chainId)` | `AsyncValue<Chain?>` | Tek zincir (ad, `brandColor`, `logoUrl`, `webUrl`, `kind`). |
| `brochureGroupsProvider(chainId)` | `AsyncValue<BrochureGroups>` | `current` ("Bu hafta"), `upcoming` ("Gelecek hafta"), `past` ("Geçmiş", son 28 gün). Sıralı gelir. |
| `brochureProvider(brochureId)` | `AsyncValue<Brochure?>` | Tek broşür (sayfalar, kapak, tarih). `null` = artık yok (süresi dolup silinmiş). |
| `productsProvider(brochureId)` | `AsyncValue<ProductFile>` (FutureProvider) | Ürün listesi; ilk izlendiğinde iner, diske önbelleklenir, ekran kapanınca bellekten atılır. |
| `favoritesProvider` | `AsyncValue<Set<String>>` | Favori zincir kimlikleri. `.notifier.toggle(chainId)` → `Future<bool>` (kaydedilemezse geri alır, `false`). |
| `isFavoriteProvider(chainId)` | `bool` | Yıldız simgesi için kısa yol. |
| `appUpdateRequiredProvider` | `bool` | Yayınlanan veri bu uygulamadan yeni bir sürüm istiyor → "uygulamayı güncelleyin" uyarısı. |
| `catalogRepositoryProvider` | `CatalogRepository` | Ekranlar yalnızca `resolve(url)` için kullanır. |
| `clockProvider` | `Clock` | `today()`; tarih metni için. Testte `Clock.fixed(...)` ile sabitlenir. |

Katalogdan türeyen bütün sağlayıcılar `catalogProvider`'ın durumunu yansıtır: ilk açılışta
*yükleniyor*, hiçbir şey yüklenemediyse *hata*, aksi halde *veri*. Yenileme sırasında ve yenileme
başarısız olduğunda eski veri yerinde kalır (ekran boşalmaz, yükleniyor'a dönmez).

## Ekran → sağlayıcı

**Ana ekran:** `orderedChainsProvider` ile ızgarayı kur; her kart `chainSummaryProvider(chain.id)`
ve `isFavoriteProvider(chain.id)` izler. Kartta yeni rozeti `summary.isNew`, "veriler eski olabilir"
işareti `summary.isStale`. Üstte `catalogProvider.value?.isStale` ise çevrimdışı şeridi,
`appUpdateRequiredProvider` ise güncelleme uyarısı. Aşağı çekip yenileme:

```dart
RefreshIndicator(
  onRefresh: () async {
    final outcome = await ref.read(catalogProvider.notifier).refresh();
    // outcome: updated | offline (önbellek gösteriliyor) | failed (eski veri duruyor)
  },
  child: ...,
)
```

**Market ekranı:** `chainProvider(id)` başlık/renk için, `brochureGroupsProvider(id)` üç bölüm için.
`chain.isWebView` ise broşür listesi yerine web görünümüne git. Kart tarihi:

```dart
final today = ref.watch(clockProvider).today();
Text(formatBrochureDates(brochure, today)); // "13–19 Kasım", "22 Ekim – 4 Kasım", "13 Kasım Cuma"
```

Kart görseli `brochure.thumbnail` (kapak, yoksa ilk sayfa, o da yoksa `null`).

**Broşür görüntüleyici:** `brochureProvider(id)`; `brochure.hasPages` ise `brochure.pages`
(`MediaImage`: `url`, `width`, `height`, `aspectRatio`). `aspectRatio` biliniyorsa görsel gelmeden
yer ayırın. "3 / 8" için `pages.length`. `brochure.hasProducts` ise ürün listesine geçiş düğmesi
gösterin (BİM'de ikisi birden var: `kind == BrochureKind.both`).

**Ürün listesi:** `productsProvider(brochureId)`. `Product`: `name`, `brand?`, `quantityText?`,
`price` (`Money`), `oldPrice?`, `discountPercent?`, `image?`, `pageIndex?` (görüntüleyicide o
sayfaya atlamak için, 0 tabanlı). Fiyat metni: `product.price.format()` → `54,95 ₺`,
`1.249,90 ₺`. Fiyatı kendiniz biçimlendirmeyin. Yeniden deneme: `ref.invalidate(productsProvider(id))`.

**Web görünümü:** `chain.webUrl` (her zaman mutlak https). Bu zincirlerin (`ChainKind.webview`:
A101, CarrefourSA, Gratis) katalogda broşürü yoktur.

## Durumları okumak

```dart
final chains = ref.watch(orderedChainsProvider);
return chains.when(
  loading: () => const YukleniyorGorunumu(),
  error: (error, _) => HataGorunumu(
    // CatalogUnavailableException: ilk açılış ve internet yok.
    // CatalogFormatException: yayınlanan dosya bozuk ve önbellek yok.
    onRetry: () => ref.read(catalogProvider.notifier).refresh(),
  ),
  data: (chains) => Izgara(chains),
);
```

- **Bayat veri:** `ref.watch(catalogProvider).value?.isStale == true` → ağ alınamadı, son kaydedilen
  katalog gösteriliyor. `fetchedAt` son başarılı indirme zamanıdır (UTC; göstermek için `.toLocal()`).
- **Zincir bazında bayat:** `chain.isStale` / `summary.isStale` → o marketin kazıyıcısı son seferde
  başarısız oldu; gösterilen broşürler son iyi kopya (`chain.lastOkAt`).
- `source == CatalogSource.cache` tek başına "çevrimdışı" demek değildir (sunucu "değişmedi" dediğinde
  de önbellek kullanılır). Şerit için **yalnızca `isStale`** kullanın.
- `source == CatalogSource.bundledSample`: geliştirme yapısı, gömülü örnek veri.
- Ürün hataları: `ProductsUnavailableException` (internet yok ve önbellek yok) ya da
  `CatalogFormatException`.

## Adres çözümleme (`resolve`)

JSON'daki görsel ve dosya adresleri ya mutlak `https://` ya da `catalog.json`'a göre göreli yoldur
(`media/sok/<id>/p01.webp`). Bir görseli yüklemeden önce **her zaman** çözün:

```dart
final repo = ref.watch(catalogRepositoryProvider);
final uri = repo.resolve(page.url);
if (uri.isBundledAsset) {
  // Yalnızca örnek veriyle çalışırken: göreli yol `asset:` adresine çözülür.
  Image.asset(uri.assetKey, errorBuilder: ...);
} else {
  // Ağ görseli (önbellekli görsel paketi burada kullanılır).
}
```

Örnek veride göreli medya dosyaları (Şok, Migros sayfaları) uygulamaya gömülü **değildir** ve
mutlak adresler örnek olarak uydurulmuştur; yani örnek veriyle görseller yüklenmez. Görsel
bileşenlerinin hata/yer tutucu durumu bu yüzden baştan tasarlanmalıdır.

## Veri kaynağı

- `--dart-define=CATALOG_BASE_URL=https://<kullanici>.github.io/<repo>/` verilirse
  `HttpCatalogRepository`: `catalog.json` ETag ile koşullu istenir, 15 sn zaman aşımı, son iyi kopya
  uygulama destek klasöründe saklanır, bozuk yanıt iyi kopyanın üzerine yazılmaz.
- Verilmezse `AssetCatalogRepository`: `assets/sample/` altındaki örnek veri. Bugünün tarihi
  2026-11-13 kabul edilerek hazırlanmıştır. Kaynak: `schema/examples/catalog.example.json` ve
  `products.example.json` (→ `products/migros-910.json`); A101 web görünümüne çevrildi;
  `products/bim-2026-11-13-cuma.json` elle yazıldı.

## Testte

```dart
final container = ProviderContainer.test(overrides: [
  catalogRepositoryProvider.overrideWithValue(sahteDepo),
  favoritesStoreProvider.overrideWithValue(MemoryFavoritesStore()),
  clockProvider.overrideWithValue(Clock.fixed(DateTime(2026, 11, 13))),
]);
```

Widget testlerinde `SharedPreferences.setMockInitialValues({})` çağırın.
