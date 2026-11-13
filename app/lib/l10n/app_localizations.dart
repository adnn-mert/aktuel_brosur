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

  /// Application name shown in the task switcher and app bar.
  ///
  /// In tr, this message translates to:
  /// **'Aktüel Broşür'**
  String get appTitle;

  /// Title of the home screen that lists the chains.
  ///
  /// In tr, this message translates to:
  /// **'Marketler'**
  String get chainsTitle;

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
  /// **'Geçmiş'**
  String get sectionPast;

  /// Shown while data loads.
  ///
  /// In tr, this message translates to:
  /// **'Yükleniyor…'**
  String get loading;

  /// Shown when nothing could be loaded (offline on first launch).
  ///
  /// In tr, this message translates to:
  /// **'Broşürler yüklenemedi. İnternet bağlantınızı kontrol edin.'**
  String get loadError;

  /// Button that retries a failed load.
  ///
  /// In tr, this message translates to:
  /// **'Tekrar dene'**
  String get retry;

  /// Banner shown when cached data is displayed because the network failed.
  ///
  /// In tr, this message translates to:
  /// **'İnternete bağlanılamadı. Son kaydedilen broşürler gösteriliyor.'**
  String get staleNotice;

  /// Empty state of the market screen.
  ///
  /// In tr, this message translates to:
  /// **'Şu an gösterilecek broşür yok.'**
  String get noBrochures;

  /// Action for chains whose catalog is shown in a web view.
  ///
  /// In tr, this message translates to:
  /// **'Marketin katalog sayfasını aç'**
  String get openChainWebsite;

  /// Number of pages in a brochure.
  ///
  /// In tr, this message translates to:
  /// **'{count, plural, =1{1 sayfa} other{{count} sayfa}}'**
  String pageCount(int count);

  /// Heading of a brochure's product list.
  ///
  /// In tr, this message translates to:
  /// **'Ürünler'**
  String get productsTitle;

  /// Shown when the published data needs a newer app version.
  ///
  /// In tr, this message translates to:
  /// **'Bu broşürleri göstermek için uygulamanın yeni sürümü gerekiyor.'**
  String get updateRequired;
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
