import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_tr.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[Locale('tr')];

  /// Application name shown on the splash, the home header and the task switcher.
  ///
  /// In tr, this message translates to:
  /// **'Çarşı Pazar'**
  String get appTitle;

  /// One-line description under the app name on the splash.
  ///
  /// In tr, this message translates to:
  /// **'Marketlerin broşürleri bir arada'**
  String get appTagline;

  /// The back button shown on every screen except home.
  ///
  /// In tr, this message translates to:
  /// **'Geri'**
  String get back;

  /// Button that retries a failed load.
  ///
  /// In tr, this message translates to:
  /// **'Tekrar dene'**
  String get retry;

  /// Guiding question at the top of the home screen.
  ///
  /// In tr, this message translates to:
  /// **'Hangi markete bakalım?'**
  String get homeQuestion;

  /// Today's date under the app name, e.g. 'Bugün 13 Kasım Cuma'.
  ///
  /// In tr, this message translates to:
  /// **'Bugün {date}'**
  String homeToday(DateTime date);

  /// Heading above the favourite markets.
  ///
  /// In tr, this message translates to:
  /// **'Sık baktıklarım'**
  String get homeFavorites;

  /// Heading above the non-favourite markets (only when there are favourites).
  ///
  /// In tr, this message translates to:
  /// **'Diğer marketler'**
  String get homeOthers;

  /// Tip shown under the market grid while there are no favourites.
  ///
  /// In tr, this message translates to:
  /// **'Sık baktığınız marketin yıldızına dokunun, hep en üstte dursun.'**
  String get homeFavoriteHint;

  /// Shown with skeleton cards during the first load.
  ///
  /// In tr, this message translates to:
  /// **'Broşürler getiriliyor…'**
  String get homeLoading;

  /// Button at the bottom of the home screen that reloads the catalog.
  ///
  /// In tr, this message translates to:
  /// **'Broşürleri yenile'**
  String get homeRefresh;

  /// Snack message after a successful refresh.
  ///
  /// In tr, this message translates to:
  /// **'Broşürler yenilendi.'**
  String get refreshUpdated;

  /// Snack message when a refresh fell back to the cached copy.
  ///
  /// In tr, this message translates to:
  /// **'İnternet yok. Kayıtlı broşürler gösteriliyor.'**
  String get refreshOffline;

  /// Snack message when a refresh failed.
  ///
  /// In tr, this message translates to:
  /// **'Yenilenemedi. Biraz sonra tekrar deneyin.'**
  String get refreshFailed;

  /// First status line of a market card that has brochures valid today.
  ///
  /// In tr, this message translates to:
  /// **'Bu hafta'**
  String get cardCurrent;

  /// Second status line of a market card: how many brochures.
  ///
  /// In tr, this message translates to:
  /// **'{count, plural, =1{1 broşür} other{{count} broşür}}'**
  String brochureCount(int count);

  /// Status line of a market card that only has upcoming brochures.
  ///
  /// In tr, this message translates to:
  /// **'Gelecek hafta'**
  String get cardUpcoming;

  /// Status line of a market card that only has past brochures.
  ///
  /// In tr, this message translates to:
  /// **'Geçmiş'**
  String get cardPast;

  /// Status line of a market card without any brochure.
  ///
  /// In tr, this message translates to:
  /// **'Broşür yok'**
  String get cardEmpty;

  /// Status line of a market whose catalog opens as a web page.
  ///
  /// In tr, this message translates to:
  /// **'Marketin sitesi'**
  String get cardWeb;

  /// Badge on a market card or brochure that appeared in the last two days.
  ///
  /// In tr, this message translates to:
  /// **'Yeni'**
  String get badgeNew;

  /// Screen-reader text for the 'Yeni' badge.
  ///
  /// In tr, this message translates to:
  /// **'Yeni broşür var'**
  String get cardNewSpoken;

  /// Screen-reader text for the outdated-data mark on a market card.
  ///
  /// In tr, this message translates to:
  /// **'Son bilgiler alınamadı'**
  String get cardStaleSpoken;

  /// Label of the empty star.
  ///
  /// In tr, this message translates to:
  /// **'{name}: sık baktıklarıma ekle'**
  String favoriteAdd(String name);

  /// Label of the filled star.
  ///
  /// In tr, this message translates to:
  /// **'{name}: sık baktıklarımdan çıkar'**
  String favoriteRemove(String name);

  /// Snack message after starring a market.
  ///
  /// In tr, this message translates to:
  /// **'{name} en üste alındı.'**
  String favoriteAdded(String name);

  /// Snack message after un-starring a market.
  ///
  /// In tr, this message translates to:
  /// **'{name} sık baktıklarınızdan çıkarıldı.'**
  String favoriteRemoved(String name);

  /// Snack message when the favourite could not be saved.
  ///
  /// In tr, this message translates to:
  /// **'Kaydedilemedi. Tekrar deneyin.'**
  String get favoriteFailed;

  /// Heading for brochures valid today.
  ///
  /// In tr, this message translates to:
  /// **'Bu hafta'**
  String get sectionCurrent;

  /// Heading for brochures that start after today.
  ///
  /// In tr, this message translates to:
  /// **'Gelecek hafta'**
  String get sectionUpcoming;

  /// Heading for brochures that ended within the last four weeks.
  ///
  /// In tr, this message translates to:
  /// **'Geçmiş broşürler'**
  String get sectionPast;

  /// Number of pages in a brochure.
  ///
  /// In tr, this message translates to:
  /// **'{count, plural, =1{1 sayfa} other{{count} sayfa}}'**
  String pageCount(int count);

  /// Number of products in a brochure's product list.
  ///
  /// In tr, this message translates to:
  /// **'{count, plural, =1{1 ürün} other{{count} ürün}}'**
  String productCount(int count);

  /// Two short facts on one line, e.g. '4 sayfa · 14 ürün' or 'Kiwi · 28 cm'.
  ///
  /// In tr, this message translates to:
  /// **'{first} · {second}'**
  String pairWithDot(String first, String second);

  /// Visible call to action on a brochure card.
  ///
  /// In tr, this message translates to:
  /// **'Aç'**
  String get open;

  /// Screen-reader hint on a brochure card.
  ///
  /// In tr, this message translates to:
  /// **'Broşürü aç'**
  String get brochureOpen;

  /// Notice on the market screen when the chain's data is outdated.
  ///
  /// In tr, this message translates to:
  /// **'Bu marketin yeni broşürleri şu an alınamıyor.'**
  String get chainStaleNotice;

  /// Second line of the outdated notice with the date of the last good data.
  ///
  /// In tr, this message translates to:
  /// **'Gördükleriniz en son alınanlar ({date}).'**
  String chainStaleDetail(DateTime date);

  /// Second line of the outdated notice when no date is known.
  ///
  /// In tr, this message translates to:
  /// **'Gördükleriniz en son alınanlar.'**
  String get chainStaleDetailUndated;

  /// Title of the empty market screen.
  ///
  /// In tr, this message translates to:
  /// **'Şu an broşür yok'**
  String get emptyChainTitle;

  /// Message of the empty market screen.
  ///
  /// In tr, this message translates to:
  /// **'{name} yeni broşür yayınlayınca burada görünecek.'**
  String emptyChainMessage(String name);

  /// Button that opens the chain's own brochure page inside the app.
  ///
  /// In tr, this message translates to:
  /// **'Marketin sitesine bak'**
  String get openChainWebsite;

  /// Shown if a market disappeared from the data while its screen was open.
  ///
  /// In tr, this message translates to:
  /// **'Bu market bulunamadı'**
  String get unknownChainTitle;

  /// Tab that shows the brochure pages.
  ///
  /// In tr, this message translates to:
  /// **'Broşür'**
  String get tabBrochure;

  /// Tab that shows the product list.
  ///
  /// In tr, this message translates to:
  /// **'Ürünler'**
  String get tabProducts;

  /// Label of the previous-page arrow.
  ///
  /// In tr, this message translates to:
  /// **'Önceki sayfa'**
  String get pagePrevious;

  /// Label of the next-page arrow.
  ///
  /// In tr, this message translates to:
  /// **'Sonraki sayfa'**
  String get pageNext;

  /// Label of the + button.
  ///
  /// In tr, this message translates to:
  /// **'Büyüt'**
  String get zoomIn;

  /// Label of the − button.
  ///
  /// In tr, this message translates to:
  /// **'Küçült'**
  String get zoomOut;

  /// Current page and page count in the viewer.
  ///
  /// In tr, this message translates to:
  /// **'{page} / {count}'**
  String pageIndicator(int page, int count);

  /// Screen-reader text of the page indicator.
  ///
  /// In tr, this message translates to:
  /// **'Sayfa {page}, toplam {count} sayfa'**
  String pageIndicatorSpoken(int page, int count);

  /// Screen-reader text of a brochure page image.
  ///
  /// In tr, this message translates to:
  /// **'Broşür sayfası {page}'**
  String pageImageSpoken(int page);

  /// Shown on a brochure page while its image loads.
  ///
  /// In tr, this message translates to:
  /// **'Sayfa yükleniyor…'**
  String get pageLoading;

  /// Title shown in place of a page image that failed to load.
  ///
  /// In tr, this message translates to:
  /// **'Bu sayfa açılamadı'**
  String get pageErrorTitle;

  /// Generic advice under a load failure.
  ///
  /// In tr, this message translates to:
  /// **'İnternet bağlantınızı kontrol edip tekrar deneyin.'**
  String get checkConnection;

  /// Shown when a brochure was removed from the data.
  ///
  /// In tr, this message translates to:
  /// **'Bu broşür artık yok'**
  String get brochureGoneTitle;

  /// Explanation under brochureGoneTitle.
  ///
  /// In tr, this message translates to:
  /// **'Süresi dolduğu için kaldırılmış olabilir.'**
  String get brochureGoneMessage;

  /// Shown while the product list loads.
  ///
  /// In tr, this message translates to:
  /// **'Ürünler getiriliyor…'**
  String get productsLoading;

  /// Title when the product list could not be loaded.
  ///
  /// In tr, this message translates to:
  /// **'Ürünler getirilemedi'**
  String get productsErrorTitle;

  /// Title when the product list is empty.
  ///
  /// In tr, this message translates to:
  /// **'Bu broşürde ürün listesi yok'**
  String get productsEmptyTitle;

  /// Discount tag on a product card.
  ///
  /// In tr, this message translates to:
  /// **'%{percent} indirim'**
  String discountPercent(int percent);

  /// Screen-reader text for the crossed-out price.
  ///
  /// In tr, this message translates to:
  /// **'Eski fiyat {price}'**
  String oldPriceSpoken(String price);

  /// Button on a product card that opens the brochure page showing it.
  ///
  /// In tr, this message translates to:
  /// **'Sayfada göster'**
  String get showOnPage;

  /// Shown while the chain's web page loads.
  ///
  /// In tr, this message translates to:
  /// **'Sayfa açılıyor…'**
  String get webLoading;

  /// Title when the chain's web page failed to load.
  ///
  /// In tr, this message translates to:
  /// **'Sayfa açılamadı'**
  String get webErrorTitle;

  /// Message when the chain's web page failed to load.
  ///
  /// In tr, this message translates to:
  /// **'{name} sitesine şu an ulaşılamıyor. İnternet bağlantınızı kontrol edin ya da sayfayı tarayıcıda açın.'**
  String webErrorMessage(String name);

  /// Button that opens the chain's page in the phone's browser.
  ///
  /// In tr, this message translates to:
  /// **'Tarayıcıda aç'**
  String get openInBrowser;

  /// Snack message when the external browser could not be started.
  ///
  /// In tr, this message translates to:
  /// **'Tarayıcı açılamadı.'**
  String get browserFailed;

  /// Button that goes one page back inside the chain's web site.
  ///
  /// In tr, this message translates to:
  /// **'Sitede geri'**
  String get webBack;

  /// Title of the full-screen state on first launch without internet.
  ///
  /// In tr, this message translates to:
  /// **'İnternete bağlanılamadı'**
  String get offlineTitle;

  /// Message of the first-launch offline state.
  ///
  /// In tr, this message translates to:
  /// **'Broşürleri getirmek için internet gerekiyor. Bağlantınızı kontrol edip tekrar deneyin.'**
  String get offlineMessage;

  /// Title when the published data is unusable and nothing is cached.
  ///
  /// In tr, this message translates to:
  /// **'Broşürler şu an gösterilemiyor'**
  String get brokenTitle;

  /// Message under brokenTitle.
  ///
  /// In tr, this message translates to:
  /// **'Bir aksaklık var. Biraz sonra tekrar deneyin.'**
  String get brokenMessage;

  /// Notice on the home screen when cached data is shown because the network failed.
  ///
  /// In tr, this message translates to:
  /// **'İnternet yok. Daha önce açtığınız broşürleri okuyabilirsiniz.'**
  String get staleNotice;

  /// When the shown data was last fetched.
  ///
  /// In tr, this message translates to:
  /// **'Son yenileme: {date}'**
  String staleDetail(DateTime date);

  /// Notice shown when the published data needs a newer app version.
  ///
  /// In tr, this message translates to:
  /// **'Bu broşürleri göstermek için uygulamanın yeni sürümü gerekiyor.'**
  String get updateRequired;

  /// Second line of the update notice.
  ///
  /// In tr, this message translates to:
  /// **'Uygulamayı güncelleyince bütün broşürler görünür.'**
  String get updateRequiredDetail;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['tr'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'tr':
      return AppLocalizationsTr();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
