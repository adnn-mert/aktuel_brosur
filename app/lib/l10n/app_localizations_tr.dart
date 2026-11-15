// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Turkish (`tr`).
class AppLocalizationsTr extends AppLocalizations {
  AppLocalizationsTr([String locale = 'tr']) : super(locale);

  @override
  String get appTitle => 'Çarşı Pazar';

  @override
  String get appTagline => 'Marketlerin broşürleri bir arada';

  @override
  String get back => 'Geri';

  @override
  String get retry => 'Tekrar dene';

  @override
  String get homeQuestion => 'Hangi markete bakalım?';

  @override
  String homeToday(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat(
      'd MMMM EEEE',
      localeName,
    );
    final String dateString = dateDateFormat.format(date);

    return 'Bugün $dateString';
  }

  @override
  String get homeFavorites => 'Sık baktıklarım';

  @override
  String get homeOthers => 'Diğer marketler';

  @override
  String get homeFavoriteHint =>
      'Sık baktığınız marketin yıldızına dokunun, hep en üstte dursun.';

  @override
  String get homeLoading => 'Broşürler getiriliyor…';

  @override
  String get homeRefresh => 'Broşürleri yenile';

  @override
  String get refreshUpdated => 'Broşürler yenilendi.';

  @override
  String get refreshOffline => 'İnternet yok. Kayıtlı broşürler gösteriliyor.';

  @override
  String get refreshFailed => 'Yenilenemedi. Biraz sonra tekrar deneyin.';

  @override
  String get cardCurrent => 'Bu hafta';

  @override
  String brochureCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count broşür',
      one: '1 broşür',
    );
    return '$_temp0';
  }

  @override
  String get cardUpcoming => 'Gelecek hafta';

  @override
  String get cardPast => 'Geçmiş';

  @override
  String get cardEmpty => 'Broşür yok';

  @override
  String get cardWeb => 'Marketin sitesi';

  @override
  String get badgeNew => 'Yeni';

  @override
  String get cardNewSpoken => 'Yeni broşür var';

  @override
  String get cardStaleSpoken => 'Son bilgiler alınamadı';

  @override
  String favoriteAdd(String name) {
    return '$name: sık baktıklarıma ekle';
  }

  @override
  String favoriteRemove(String name) {
    return '$name: sık baktıklarımdan çıkar';
  }

  @override
  String favoriteAdded(String name) {
    return '$name en üste alındı.';
  }

  @override
  String favoriteRemoved(String name) {
    return '$name sık baktıklarınızdan çıkarıldı.';
  }

  @override
  String get favoriteFailed => 'Kaydedilemedi. Tekrar deneyin.';

  @override
  String get sectionCurrent => 'Bu hafta';

  @override
  String get sectionUpcoming => 'Gelecek hafta';

  @override
  String get sectionPast => 'Geçmiş broşürler';

  @override
  String pageCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count sayfa',
      one: '1 sayfa',
    );
    return '$_temp0';
  }

  @override
  String productCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count ürün',
      one: '1 ürün',
    );
    return '$_temp0';
  }

  @override
  String pairWithDot(String first, String second) {
    return '$first · $second';
  }

  @override
  String get open => 'Aç';

  @override
  String get brochureOpen => 'Broşürü aç';

  @override
  String get chainStaleNotice =>
      'Bu marketin yeni broşürleri şu an alınamıyor.';

  @override
  String chainStaleDetail(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat(
      'd MMMM',
      localeName,
    );
    final String dateString = dateDateFormat.format(date);

    return 'Gördükleriniz en son alınanlar ($dateString).';
  }

  @override
  String get chainStaleDetailUndated => 'Gördükleriniz en son alınanlar.';

  @override
  String get emptyChainTitle => 'Şu an broşür yok';

  @override
  String emptyChainMessage(String name) {
    return '$name yeni broşür yayınlayınca burada görünecek.';
  }

  @override
  String get openChainWebsite => 'Marketin sitesine bak';

  @override
  String get unknownChainTitle => 'Bu market bulunamadı';

  @override
  String get tabBrochure => 'Broşür';

  @override
  String get tabProducts => 'Ürünler';

  @override
  String get pagePrevious => 'Önceki sayfa';

  @override
  String get pageNext => 'Sonraki sayfa';

  @override
  String get zoomIn => 'Büyüt';

  @override
  String get zoomOut => 'Küçült';

  @override
  String pageIndicator(int page, int count) {
    return '$page / $count';
  }

  @override
  String pageIndicatorSpoken(int page, int count) {
    return 'Sayfa $page, toplam $count sayfa';
  }

  @override
  String get pagePickerTitle => 'Sayfa seç';

  @override
  String pagePickerOpenSpoken(int page, int count) {
    return 'Sayfa $page, toplam $count sayfa. Başka sayfaya gitmek için dokunun';
  }

  @override
  String pageNumberSpoken(int page) {
    return 'Sayfa $page';
  }

  @override
  String pageNumberCurrentSpoken(int page) {
    return 'Sayfa $page, şu an buradasınız';
  }

  @override
  String pageImageSpoken(int page) {
    return 'Broşür sayfası $page';
  }

  @override
  String get pageLoading => 'Sayfa yükleniyor…';

  @override
  String get pageErrorTitle => 'Bu sayfa açılamadı';

  @override
  String get checkConnection =>
      'İnternet bağlantınızı kontrol edip tekrar deneyin.';

  @override
  String get brochureGoneTitle => 'Bu broşür artık yok';

  @override
  String get brochureGoneMessage => 'Süresi dolduğu için kaldırılmış olabilir.';

  @override
  String get productsLoading => 'Ürünler getiriliyor…';

  @override
  String get productsErrorTitle => 'Ürünler getirilemedi';

  @override
  String get productsEmptyTitle => 'Bu broşürde ürün listesi yok';

  @override
  String discountPercent(int percent) {
    return '%$percent indirim';
  }

  @override
  String oldPriceSpoken(String price) {
    return 'Eski fiyat $price';
  }

  @override
  String priceWithUnit(String price, String unit) {
    return '$price, $unit';
  }

  @override
  String memberPriceSpoken(String label, String price) {
    return '$label: $price';
  }

  @override
  String get showOnPage => 'Sayfada göster';

  @override
  String get webLoading => 'Sayfa açılıyor…';

  @override
  String get webErrorTitle => 'Sayfa açılamadı';

  @override
  String webErrorMessage(String name) {
    return '$name sitesine şu an ulaşılamıyor. İnternet bağlantınızı kontrol edin ya da sayfayı tarayıcıda açın.';
  }

  @override
  String get openInBrowser => 'Tarayıcıda aç';

  @override
  String get browserFailed => 'Tarayıcı açılamadı.';

  @override
  String get webBack => 'Sitede geri';

  @override
  String get offlineTitle => 'İnternete bağlanılamadı';

  @override
  String get offlineMessage =>
      'Broşürleri getirmek için internet gerekiyor. Bağlantınızı kontrol edip tekrar deneyin.';

  @override
  String get brokenTitle => 'Broşürler şu an gösterilemiyor';

  @override
  String get brokenMessage => 'Bir aksaklık var. Biraz sonra tekrar deneyin.';

  @override
  String get staleNotice =>
      'İnternet yok. Daha önce açtığınız broşürleri okuyabilirsiniz.';

  @override
  String staleDetail(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat(
      'd MMMM EEEE',
      localeName,
    );
    final String dateString = dateDateFormat.format(date);

    return 'Son yenileme: $dateString';
  }

  @override
  String get updateRequired =>
      'Bu broşürleri göstermek için uygulamanın yeni sürümü gerekiyor.';

  @override
  String get updateRequiredDetail =>
      'Uygulamayı güncelleyince bütün broşürler görünür.';

  @override
  String get searchTitle => 'Ürün ara';

  @override
  String get searchEntryHint => 'Hangi markette kaç lira?';

  @override
  String get searchEntrySpoken => 'Ürün ara. Hangi markette kaç lira, bakın.';

  @override
  String get searchFieldHint => 'Ürün adı yazın';

  @override
  String get searchFieldSpoken => 'Aranacak ürünün adı';

  @override
  String get searchClear => 'Yazıyı sil';

  @override
  String get searchIdleTitle => 'Ne arıyorsunuz?';

  @override
  String get searchIdleMessage =>
      'Ürünün adını yazın. Broşürlerde hangi markette kaç lira olduğunu ucuzdan pahalıya sıralarız.';

  @override
  String get searchTooShort => 'En az iki harf yazın.';

  @override
  String get searchExamplesTitle => 'Ya da birine dokunun';

  @override
  String get searchExamples =>
      'Süt, Çay, Peynir, Yumurta, Yağ, Şeker, Makarna, Pirinç, Deterjan, Kahve, Tavuk, Şampuan';

  @override
  String searchExampleSpoken(String word) {
    return '$word ara';
  }

  @override
  String get searchCoverageTitle => 'Arama yapılan marketler';

  @override
  String get searchCoverageNote =>
      'Diğer marketler broşürlerini resim olarak yayınlıyor; onların içinde arama yapılamıyor. Onlara ana ekrandan bakabilirsiniz.';

  @override
  String get searchPriceNote =>
      'Fiyatlar broşürde yazdığı gibidir; broşürün tarihlerinde geçerlidir.';

  @override
  String get searchSortNote =>
      'En ucuzu en üstte. Paket boyları farklı olabilir.';

  @override
  String searchResultCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count ürün bulundu',
      one: '1 ürün bulundu',
    );
    return '$_temp0';
  }

  @override
  String get searchLoading => 'Broşürlerdeki ürünler hazırlanıyor…';

  @override
  String searchNoResultsTitle(String query) {
    return '“$query” bulunamadı';
  }

  @override
  String get searchNoResultsMessage =>
      'Aranan broşürlerde bu adla bir ürün yok. Sözcüğün yalnızca başını yazmayı deneyin; örneğin “ekmek” yerine “ekme”.';

  @override
  String searchNoResultsCoverage(String names) {
    return 'Arama yapılan marketler: $names. Diğer marketlerin broşürlerinde henüz arama yapılamıyor.';
  }

  @override
  String get searchNewSearch => 'Başka ürün ara';

  @override
  String get searchErrorTitle => 'Arama şu an yapılamıyor';

  @override
  String get searchEmptyIndexTitle => 'Şu an aranabilecek broşür yok';

  @override
  String get searchEmptyIndexMessage =>
      'Marketler fiyatlarını yazı olarak yayınlayınca burada arayabilirsiniz. Broşürlere ana ekrandan bakabilirsiniz.';

  @override
  String get searchOfflineNotice =>
      'İnternet yok. Yalnızca daha önce açtığınız broşürlerde aranıyor.';

  @override
  String get searchOpenSpoken => 'Broşürde görmek için dokunun';

  @override
  String get searchUpcoming => 'Henüz başlamadı';

  @override
  String get searchedProductTitle => 'Aradığınız ürün';

  @override
  String get allProductsTitle => 'Bu broşürdeki bütün ürünler';

  @override
  String get searchOfflineEmptyMessage =>
      'İnternet yokken yalnızca daha önce açtığınız broşürlerde aranabiliyor. Bağlantınızı kontrol edip tekrar deneyin.';

  @override
  String get notifyOffTitle => 'Yeni broşür çıkınca haber ver';

  @override
  String get notifyOffDetail => 'Bildirim şu an kapalı';

  @override
  String get notifyOffSpoken =>
      'Yeni broşür çıkınca haber ver. Bildirim şu an kapalı. Açmak için dokunun.';

  @override
  String get notifyOnTitle => 'Yeni broşür bildirimi açık';

  @override
  String notifyOnDetail(String names) {
    return '$names yeni broşür çıkarınca telefonunuza bildirim gelir.';
  }

  @override
  String get notifyTurnOff => 'Bildirimi kapat';

  @override
  String get notifyBlockedTitle => 'Bildirimler telefonda kapalı';

  @override
  String get notifyBlockedDetail =>
      'Yeni broşür haberi almak için telefonun ayarlarından bu uygulamaya izin vermeniz gerekiyor.';

  @override
  String get notifyOpenSettings => 'Telefon ayarlarını aç';

  @override
  String get notifySettingsFailed =>
      'Telefonun ayarları açılamadı. Aşağıdaki adımları izleyin.';

  @override
  String get notifyBlockedHowTo => 'Elle nasıl açılır?';

  @override
  String get notifyBlockedHideSteps => 'Adımları gizle';

  @override
  String get notifyBlockedStep1 => 'Telefonun Ayarlar uygulamasını açın.';

  @override
  String notifyBlockedStep2(String app) {
    return '“Uygulamalar”a, sonra “$app”a dokunun.';
  }

  @override
  String get notifyBlockedStep3 =>
      '“Bildirimler”e dokunup açın, sonra buraya geri dönün.';

  @override
  String notifyStepSpoken(int number, String text) {
    return 'Adım $number: $text';
  }

  @override
  String get notifyOfferTitle => 'Yeni broşür çıkınca haber verelim mi?';

  @override
  String notifyOfferMessage(String names) {
    return '$names yeni broşür çıkarınca telefonunuza kısa bir bildirim gelir.';
  }

  @override
  String get notifyOfferPermissionNote =>
      'Telefon izin sorarsa “İzin ver”e dokunun.';

  @override
  String get notifyOfferYes => 'Evet, haber ver';

  @override
  String get notifyOfferNo => 'Şimdi değil';

  @override
  String get notifyTurnedOn => 'Tamam. Yeni broşür çıkınca haber vereceğiz.';

  @override
  String get notifyNotAllowed =>
      'Telefon izin vermediği için bildirim açılmadı.';

  @override
  String get notifyTurnedOff => 'Bildirim kapatıldı.';

  @override
  String get notifyFailed =>
      'Bildirim şu an ayarlanamadı. Biraz sonra tekrar deneyin.';

  @override
  String nameListTwo(String first, String second) {
    return '$first ve $second';
  }

  @override
  String nameListThree(String first, String second, String third) {
    return '$first, $second ve $third';
  }

  @override
  String favoriteChainsCount(int count) {
    return 'Sık baktığınız $count market';
  }
}
